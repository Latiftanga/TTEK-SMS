"""phase6: StudentFeeSummary DB trigger

Revision ID: e5f0a2d91c74
Revises: c4e2d8b1f903
Create Date: 2026-06-13
"""
from alembic import op

revision = "e5f0a2d91c74"
down_revision = "c4e2d8b1f903"
branch_labels = None
depends_on = None

_CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION update_student_fee_summary()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_student_id  UUID;
    v_term_id     UUID;
    v_school_id   UUID;
    v_total_due   NUMERIC(12,2);
    v_total_paid  NUMERIC(12,2);
    v_total_disc  NUMERIC(12,2);
    v_last_pay    DATE;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_student_id := OLD.student_id;
        v_term_id    := OLD.academic_term_id;
        v_school_id  := OLD.school_id;
    ELSE
        v_student_id := NEW.student_id;
        v_term_id    := NEW.academic_term_id;
        v_school_id  := NEW.school_id;
    END IF;

    SELECT COALESCE(SUM(CASE WHEN NOT is_waived THEN amount_due ELSE 0 END), 0)
      INTO v_total_due
      FROM student_fee_record
     WHERE student_id = v_student_id
       AND academic_term_id = v_term_id;

    SELECT COALESCE(SUM(amount_paid), 0), MAX(payment_date)
      INTO v_total_paid, v_last_pay
      FROM fee_payment
     WHERE student_id = v_student_id
       AND academic_term_id = v_term_id;

    SELECT COALESCE(SUM(
               CASE WHEN fd.amount IS NOT NULL
                    THEN fd.amount
                    ELSE sfr.amount_due * fd.percentage / 100
               END), 0)
      INTO v_total_disc
      FROM fee_discount fd
      JOIN student_fee_record sfr ON sfr.id = fd.fee_record_id
     WHERE fd.student_id = v_student_id
       AND fd.academic_term_id = v_term_id;

    INSERT INTO student_fee_summary (
        id, school_id, student_id, academic_term_id,
        total_due, total_paid, total_discounted,
        last_payment_date, updated_at
    )
    VALUES (
        gen_random_uuid(), v_school_id, v_student_id, v_term_id,
        v_total_due, v_total_paid, v_total_disc,
        v_last_pay, NOW()
    )
    ON CONFLICT (student_id, academic_term_id) DO UPDATE SET
        total_due         = EXCLUDED.total_due,
        total_paid        = EXCLUDED.total_paid,
        total_discounted  = EXCLUDED.total_discounted,
        last_payment_date = EXCLUDED.last_payment_date,
        updated_at        = EXCLUDED.updated_at;

    RETURN NULL;
END;
$$;
"""

_TRIGGER_RECORD = """
CREATE TRIGGER trg_fee_summary_on_record
AFTER INSERT OR UPDATE OR DELETE ON student_fee_record
FOR EACH ROW EXECUTE FUNCTION update_student_fee_summary()
"""

_TRIGGER_PAYMENT = """
CREATE TRIGGER trg_fee_summary_on_payment
AFTER INSERT OR UPDATE OR DELETE ON fee_payment
FOR EACH ROW EXECUTE FUNCTION update_student_fee_summary()
"""

_TRIGGER_DISCOUNT = """
CREATE TRIGGER trg_fee_summary_on_discount
AFTER INSERT OR UPDATE OR DELETE ON fee_discount
FOR EACH ROW EXECUTE FUNCTION update_student_fee_summary()
"""


def upgrade() -> None:
    op.execute(_CREATE_FUNCTION)
    op.execute(_TRIGGER_RECORD)
    op.execute(_TRIGGER_PAYMENT)
    op.execute(_TRIGGER_DISCOUNT)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_fee_summary_on_record ON student_fee_record")
    op.execute("DROP TRIGGER IF EXISTS trg_fee_summary_on_payment ON fee_payment")
    op.execute("DROP TRIGGER IF EXISTS trg_fee_summary_on_discount ON fee_discount")
    op.execute("DROP FUNCTION IF EXISTS update_student_fee_summary()")
