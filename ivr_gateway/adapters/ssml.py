from defusedxml import ElementTree as ET

from twilio.twiml import TwiML


class SSML(TwiML):

    def __init__(self, message=None, **kwargs):
        super(SSML, self).__init__(**kwargs)
        self.name = 'Say'
        if message is not None:
            self.value = message
            try:
                self.xml_value = ET.fromstring(f'<?xml version="1.0"?>{self.value}')
            except ET.ParseError:
                self.xml_value = ET.fromstring(f'<?xml version="1.0"?><Say>{self.value}</Say>')
            root_tag = self.xml_value.tag
            if root_tag == "speak":
                self.xml_value.tag = "Say"

    def xml(self):
        return self.xml_value
