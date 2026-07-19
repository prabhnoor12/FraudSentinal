import pyotp
import qrcode
import io
import base64
from typing import List, Tuple
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
import os
import hashlib
from dotenv import load_dotenv

load_dotenv()

from models.user_models import User
from utils.exception_handling_utils import ValidationError

# Fernet key for encrypting MFA secrets
MFA_ENCRYPTION_KEY = os.getenv("MFA_ENCRYPTION_KEY")
if MFA_ENCRYPTION_KEY:
    fernet = Fernet(MFA_ENCRYPTION_KEY.encode())
else:
    # Fallback for development only, should be strictly enforced in prod
    fernet = None


class MFAService:
    @staticmethod
    def generate_setup_data(user: User) -> Tuple[str, str]:
        """Generate a new TOTP secret and QR code for the user."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email, issuer_name="FraudSentinal"
        )

        # Generate QR Code image
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()

        return secret, f"data:image/png;base64,{qr_code_base64}"

    @staticmethod
    def verify_and_enable(db: Session, user: User, secret: str, code: str) -> List[str]:
        """Verify the first MFA code and enable MFA for the user."""
        totp = pyotp.TOTP(secret)
        if not totp.verify(code):
            raise ValidationError("Invalid MFA verification code")

        # Encrypt secret
        if fernet:
            encrypted_secret = fernet.encrypt(secret.encode()).decode()
        else:
            encrypted_secret = secret  # Insecure fallback

        # Generate backup codes
        backup_codes = [pyotp.random_base32()[:8] for _ in range(5)]
        backup_codes_hash = ",".join(
            [hashlib.sha256(c.encode()).hexdigest() for c in backup_codes]
        )

        user.mfa_secret = encrypted_secret
        user.mfa_enabled = True
        user.mfa_last_bound_at = datetime.now(UTC)
        user.mfa_backup_codes_hash = backup_codes_hash

        db.add(user)
        db.commit()

        return backup_codes

    @staticmethod
    def verify_code(user: User, code: str) -> bool:
        """Verify a TOTP code against the user's stored secret."""
        if not user.mfa_enabled or not user.mfa_secret:
            return False

        # Decrypt secret
        try:
            if fernet:
                secret = fernet.decrypt(user.mfa_secret.encode()).decode()
            else:
                secret = user.mfa_secret
        except Exception:
            return False

        totp = pyotp.TOTP(secret)
        return totp.verify(code)

    @staticmethod
    def verify_backup_code(db: Session, user: User, code: str) -> bool:
        """Verify and consume a backup code."""
        if not user.mfa_backup_codes_hash:
            return False

        code_hash = hashlib.sha256(code.encode()).hexdigest()
        hashes = user.mfa_backup_codes_hash.split(",")

        if code_hash in hashes:
            hashes.remove(code_hash)
            user.mfa_backup_codes_hash = ",".join(hashes)
            db.add(user)
            db.commit()
            return True

        return False
