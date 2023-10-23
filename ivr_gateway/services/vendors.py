from sqlalchemy import orm
from typing import List

from ivr_gateway.models.vendors import VendorResponse


class VendorService:

    def __init__(self, db_session: orm.Session):
        self.db_session = db_session

    def get_vendor_responses_by_name(self, vendor_name: str) -> List[VendorResponse]:
        return (self.db_session.query(VendorResponse)
                .filter(VendorResponse.vendor == vendor_name)
                .all())

    def get_vendor_error_responses_by_name(self, vendor_name: str) -> List[VendorResponse]:
        return (self.db_session.query(VendorResponse)
                .filter(VendorResponse.vendor == vendor_name)
                .filter(VendorResponse.status_code >= 400)
                .all())
