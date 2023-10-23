from twilio.twiml.voice_response import VoiceResponse

from ivr_gateway.adapters.ssml import SSML


class TestSSML:

    def test_ssml(self):
        ssml = SSML('hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.')
        assert str(ssml) == '<?xml version="1.0" encoding="UTF-8"?><Say>hello from <phoneme alphabet="ipa" ' \
                            'ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say>'
        speak_ssml = SSML('<speak>hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.</speak>')
        assert str(speak_ssml) == '<?xml version="1.0" encoding="UTF-8"?><Say>hello from <phoneme alphabet="ipa" ' \
                                  'ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say>'
        say_ssml = SSML('<Say>hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.</Say>')
        assert str(say_ssml) == '<?xml version="1.0" encoding="UTF-8"?><Say>hello from <phoneme alphabet="ipa" ' \
                                'ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say>'
        speak_keys_ssml = SSML(
            '<speak voice="Polly.Joanna">hello from <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme>.</speak>')
        assert str(speak_keys_ssml) == '<?xml version="1.0" encoding="UTF-8"?><Say voice="Polly.Joanna">hello from' \
                                       ' <phoneme alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say>'
        voice_response = VoiceResponse()
        voice_response.nest(ssml)
        assert str(voice_response) == '<?xml version="1.0" encoding="UTF-8"?><Response><Say>hello from <phoneme ' \
                                      'alphabet="ipa" ph="&#601;&#712;v&#593;nt">Iivr</phoneme>.</Say></Response>'
