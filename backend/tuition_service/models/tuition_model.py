from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class TuitionBill(BaseModel):
    student_id: str
    student_name: str
    amount: Decimal
    status: Literal["UNPAID", "PAID"]
