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
from utils.security_utils import derive_fernet_key


def get_mfa_cipher() -> Fernet:
    """Return the cipher used to protect stored MFA secrets."""
    key = os.getenv("MFA_ENCRYPTION_KEY")
    if key:
        return Fernet(key.encode())

    secret_key = os.getenv("SECRET_KEY")
    if secret_key:
        return Fernet(derive_fernet_key(secret_key).encode())

    raise ValueError("MFA encryption is not configured")


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

        cipher = get_mfa_cipher()
        encrypted_secret = cipher.encrypt(secret.encode()).decode()

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

        try:
            secret = get_mfa_cipher().decrypt(user.mfa_secret.encode()).decode()
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
