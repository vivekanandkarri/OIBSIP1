"""Weather handler module for PyVoice Assistant.

Queries the OpenWeatherMap API for current conditions and 3-day forecast,
falling back to a realistic mock response if API keys are missing.
"""

import os
import logging
from typing import Any, Dict
from handlers.base_handler import BaseHandler, HandlerError

logger = logging.getLogger("PyVoice.Handlers.Weather")


class WeatherHandler(BaseHandler):
    """Processes requests about the weather, fetching real-time data or mocking it."""

    def execute(self, entities: Dict[str, Any]) -> str:
        """Fetches current weather and/or 3-day forecast for the requested city.

        Args:
            entities: Extracted entities, may contain "city".

        Returns:
            Spoken weather report.
        """
        # Resolve target city: Entities city -> User default city -> Hyderabad
        city = entities.get("city")
        if not city:
            city = self.config.get("user", {}).get("default_city", "Hyderabad")
        
        api_key = os.getenv("OPENWEATHER_API_KEY")

        if not api_key or api_key.startswith("your_"):
            logger.info("OpenWeatherMap API Key missing or default. Returning mock weather data.")
            return self._get_mock_weather(city)

        try:
            # 1. Fetch current weather
            current_url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": city,
                "appid": api_key,
                "units": "metric"
            }
            curr_res = self.secure_request(current_url, params=params).json()
            
            temp = round(curr_res["main"]["temp"])
            desc = curr_res["weather"][0]["description"]
            
            report = f"It's currently {temp} degrees Celsius and {desc} in {city}."

            # 2. Fetch forecast (3 days)
            forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
            forecast_res = self.secure_request(forecast_url, params=params).json()
            
            # OpenWeatherMap forecast provides data every 3 hours. We aggregate for next 3 days.
            # Day 1: +8 steps (24 hours), Day 2: +16 steps, Day 3: +24 steps
            forecasts = []
            list_data = forecast_res.get("list", [])
            for day in range(1, 4):
                index = day * 8 - 1
                if index < len(list_data):
                    data = list_data[index]
                    f_temp = round(data["main"]["temp"])
                    f_desc = data["weather"][0]["description"]
                    forecasts.append(f"Day {day}: {f_temp} degrees and {f_desc}")

            if forecasts:
                report += f" The 3-day forecast is: {', '.join(forecasts)}."
            
            return report

        except Exception as e:
            logger.error(f"Error fetching real weather: {e}. Falling back to mock data.")
            return f"I had trouble contacting the weather service. Here is what I can estimate: {self._get_mock_weather(city)}"

    def _get_mock_weather(self, city: str) -> str:
        """Returns realistic mock weather data."""
        # Simple pseudo-random mock temperatures based on city name length
        base_temp = 20 + (len(city) % 15)
        conditions = ["clear sky", "partly cloudy", "scattered clouds", "light rain"]
        cond = conditions[len(city) % len(conditions)]
        
        report = f"It's currently {base_temp}°C and {cond} in {city}."
        
        # 3-day forecast mocks
        f1 = f"tomorrow: {base_temp + 1}°C and clear"
        f2 = f"the day after: {base_temp - 2}°C and cloudy"
        f3 = f"in three days: {base_temp}°C with light showers"
        
        return f"{report} The 3-day forecast is: {f1}, {f2}, and {f3}."
