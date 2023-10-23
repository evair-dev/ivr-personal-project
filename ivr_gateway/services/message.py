import os
from typing import Optional
import yaml

from ivr_gateway.logger import ivr_logger



class SimpleMessageService:

    def get_message_by_key(self, name: str) -> Optional[str]:
        try:
            if not name:
                return None

            return self.message_config[name]

        # in case there is an issue reading file we want to ensure that a call doesn't drop because of an app error
        except Exception as e:
            ivr_logger.error(str(e))
            return None

    @property
    def config_path(self):
        return f"commands/configs/{os.getenv('IVR_APP_ENV')}/message_config.yml"


    @property
    def message_config(self):
        with open(self.config_path) as file:
            return yaml.safe_load(file.read())
