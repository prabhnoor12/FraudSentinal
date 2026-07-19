from sqlalchemy.orm import Session
from sqlalchemy import func
from models.transaction_models import Transaction
from models.decision_models import Decision
from models.review_case_models import ReviewCase, ReviewCaseStatus
from datetime import datetime, timedelta, UTC

class OrganisationSummaryService:
    @staticmethod
    def get_dashboard_summary(db: Session, organisation_id: int):
        """Get a summary of activity for the organisation dashboard."""
        
        # 1. Transaction Stats (Last 30 days)
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        
        total_transactions = db.query(func.count(Transaction.id)).filter(
            Transaction.organisation_id == organisation_id,
            Transaction.created_at >= thirty_days_ago
        ).scalar() or 0
        
        # 2. Decision distribution
        decisions = db.query(
            Decision.decision, func.count(Decision.id)
        ).filter(
            Decision.organisation_id == organisation_id,
            Decision.created_at >= thirty_days_ago
        ).group_by(Decision.decision).all()
        
        # 3. Pending Cases
        pending_cases = db.query(func.count(ReviewCase.id)).filter(
            ReviewCase.organisation_id == organisation_id,
            ReviewCase.status == ReviewCaseStatus.open
        ).scalar() or 0
        
        # 4. Recent High Risk Transactions
        recent_high_risk = db.query(Transaction).join(Decision).filter(
            Transaction.organisation_id == organisation_id,
            Decision.risk_score >= 70
        ).order_by(Transaction.created_at.desc()).limit(5).all()
        
        return {
            "period_days": 30,
            "total_transactions": total_transactions,
            "decision_distribution": dict(decisions),
            "pending_cases_count": pending_cases,
            "recent_high_risk_transactions": [
                {
                    "id": tx.id,
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "created_at": tx.created_at.isoformat()
                } for tx in recent_high_risk
            ]
        }
