"""Smart Home handler module for PyVoice Assistant.

Integrates with the Home Assistant REST API for device controls and queries,
falling back to a local device state dictionary if API tokens are missing.
"""

import os
import logging
from typing import Any, Dict
from handlers.base_handler import BaseHandler, HandlerError

logger = logging.getLogger("PyVoice.Handlers.SmartHome")


class SmartHomeHandler(BaseHandler):
    """Controls and checks status of smart home devices (lights, thermostats, etc.)."""

    # Device Mock DB to preserve states between calls in mock mode
    _MOCK_DEVICES = {
        "light": {
            "living room": "off",
            "bedroom": "off",
            "kitchen": "off"
        },
        "thermostat": {
            "temperature": 22,
            "mode": "auto"
        }
    }

    def execute(self, entities: Dict[str, Any]) -> str:
        """Processes smart home commands like 'turn on bedroom light' or 'status'.

        Args:
            entities: Dictionary containing device_type, device_action, device_value.

        Returns:
            Confirmation statement of command execution.
        """
        device_type = entities.get("device_type", "light")
        action = entities.get("device_action")
        value = entities.get("device_value")

        # Resolve Home Assistant configuration from environment
        ha_url = os.getenv("HOME_ASSISTANT_URL", "http://localhost:8123/api")
        ha_token = os.getenv("HOME_ASSISTANT_TOKEN")

        # Fallback to local mock if no API token provided
        if not ha_token or ha_token.startswith("your_"):
            logger.info("Home Assistant token missing. Operating in MOCK mode.")
            return self._execute_mock(device_type, action, value)

        # Standard HA API logic
        try:
            headers = {
                "Authorization": f"Bearer {ha_token}",
                "Content-Type": "application/json"
            }

            if action == "turn_on" or action == "turn_off":
                # Determine entity domain & service
                domain = "light" if device_type == "light" else "homeassistant"
                service = "turn_on" if action == "turn_on" else "turn_off"
                url = f"{ha_url}/services/{domain}/{service}"
                
                # We mock/target general entity matching device type
                entity_id = f"{domain}.voice_control_{device_type}"
                payload = {"entity_id": entity_id}
                
                logger.info(f"Home Assistant Request: {method} {url} with {payload}")
                self.secure_request(url, method="POST", headers=headers, json_data=payload)
                
                state_str = "on" if action == "turn_on" else "off"
                return f"I have turned the {device_type} {state_str}."

            elif action == "set" and device_type in ("thermostat", "ac", "heating"):
                if not value:
                    raise HandlerError("What temperature would you like me to set the thermostat to?")
                
                url = f"{ha_url}/services/climate/set_temperature"
                entity_id = "climate.main_thermostat"
                payload = {"entity_id": entity_id, "temperature": value}

                self.secure_request(url, method="POST", headers=headers, json_data=payload)
                return f"I have set the thermostat temperature to {value} degrees."

            elif action == "status":
                # Check state of main entity
                entity_id = f"light.living_room" if device_type == "light" else "climate.main_thermostat"
                url = f"{ha_url}/states/{entity_id}"
                
                res = self.secure_request(url, method="GET", headers=headers).json()
                state = res.get("state", "unknown")
                
                if device_type == "light":
                    return f"The lights are currently {state}."
                elif device_type == "thermostat":
                    current_temp = res.get("attributes", {}).get("current_temperature", "unknown")
                    return f"The thermostat is currently set to {state} with a room temperature of {current_temp} degrees."
                
                return f"The {device_type} state is currently {state}."
            
            else:
                raise HandlerError(f"I'm not sure how to perform the action '{action}' on device '{device_type}'.")

        except Exception as e:
            logger.error(f"Home Assistant API communication failed: {e}. Falling back to Mock.")
            return f"Unable to reach Home Assistant server. (Local State Fallback): {self._execute_mock(device_type, action, value)}"

    def _execute_mock(self, device_type: str, action: Optional[str], value: Optional[int]) -> str:
        """Maintains state and runs commands against a mock device dictionary."""
        # Normalize types
        if device_type not in self._MOCK_DEVICES:
            # Create dynamic mock devices on the fly
            self._MOCK_DEVICES[device_type] = {"state": "off"}

        if action == "turn_on":
            if device_type == "light":
                # Turn all lights on
                for k in self._MOCK_DEVICES["light"]:
                    self._MOCK_DEVICES["light"][k] = "on"
                return "I have turned the lights on."
            else:
                self._MOCK_DEVICES[device_type]["state"] = "on"
                return f"I have activated the {device_type}."

        elif action == "turn_off":
            if device_type == "light":
                # Turn all lights off
                for k in self._MOCK_DEVICES["light"]:
                    self._MOCK_DEVICES["light"][k] = "off"
                return "I have turned the lights off."
            else:
                self._MOCK_DEVICES[device_type]["state"] = "off"
                return f"I have turned off the {device_type}."

        elif action == "set" and device_type in ("thermostat", "ac", "heating"):
            if not value:
                return "What temperature would you like me to set the thermostat to?"
            self._MOCK_DEVICES["thermostat"]["temperature"] = value
            return f"I've set the thermostat to {value} degrees Celsius."

        elif action == "status":
            if device_type == "light":
                # Summarize lights states
                states = [f"{k} is {v}" for k, v in self._MOCK_DEVICES["light"].items()]
                return f"Current lights status: {', and '.join(states)}."
            elif device_type == "thermostat":
                temp = self._MOCK_DEVICES["thermostat"]["temperature"]
                return f"The thermostat is currently set to {temp} degrees Celsius."
            
            state = self._MOCK_DEVICES[device_type].get("state", "off")
            return f"The {device_type} is currently {state}."

        # Default fallback
        return f"I recognized the device '{device_type}', but no action was specified. You can say 'turn on the lights' or 'check thermostat status'."
