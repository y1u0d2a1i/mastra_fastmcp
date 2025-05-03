import httpx
from pydantic import BaseModel, Field
from typing import List, Optional
from fastmcp import FastMCP, Client

mcp = FastMCP("MCP Servers to get weather data")

class GeocodingResult(BaseModel):
    latitude: float
    longitude: float
    name: str

class GeocodingResponse(BaseModel):
    results: Optional[List[GeocodingResult]] = None

class WeatherCurrent(BaseModel):
    time: str
    temperature_2m: float
    apparent_temperature: float
    relative_humidity_2m: int = Field(..., alias='relative_humidity_2m')
    wind_speed_10m: float
    wind_gusts_10m: float
    weather_code: int

class WeatherResponse(BaseModel):
    current: WeatherCurrent

class WeatherInput(BaseModel):
    location: str = Field(..., description="City name")

class WeatherOutput(BaseModel):
    temperature: float
    feels_like: float = Field(..., alias='feelsLike')
    humidity: int
    wind_speed: float = Field(..., alias='windSpeed')
    wind_gust: float = Field(..., alias='windGust')
    conditions: str
    location: str

# --- Helper Function ---

def get_weather_condition(code: int) -> str:
    conditions = {
        0: 'Clear sky',
        1: 'Mainly clear',
        2: 'Partly cloudy',
        3: 'Overcast',
        45: 'Foggy',
        48: 'Depositing rime fog',
        51: 'Light drizzle',
        53: 'Moderate drizzle',
        55: 'Dense drizzle',
        56: 'Light freezing drizzle',
        57: 'Dense freezing drizzle',
        61: 'Slight rain',
        63: 'Moderate rain',
        65: 'Heavy rain',
        66: 'Light freezing rain',
        67: 'Heavy freezing rain',
        71: 'Slight snow fall',
        73: 'Moderate snow fall',
        75: 'Heavy snow fall',
        77: 'Snow grains',
        80: 'Slight rain showers',
        81: 'Moderate rain showers',
        82: 'Violent rain showers',
        85: 'Slight snow showers',
        86: 'Heavy snow showers',
        95: 'Thunderstorm',
        96: 'Thunderstorm with slight hail',
        99: 'Thunderstorm with heavy hail',
    }
    return conditions.get(code, 'Unknown')

# --- Core Logic ---

@mcp.tool()
async def get_weather(location: str) -> WeatherOutput:
    """Gets the current weather for a given location using Open-Meteo APIs."""
    async with httpx.AsyncClient() as client:
        # 1. Geocoding: Get coordinates for the location
        geocoding_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
        try:
            geo_response = await client.get(geocoding_url)
            geo_response.raise_for_status() # Raise an exception for bad status codes
            geocoding_data = GeocodingResponse.model_validate(geo_response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"Geocoding API request failed: {e.response.status_code}") from e
        except Exception as e:
            raise Exception(f"Failed to parse geocoding response: {e}") from e


        if not geocoding_data.results:
            raise ValueError(f"Location '{location}' not found")

        geo_result = geocoding_data.results[0]
        latitude = geo_result.latitude
        longitude = geo_result.longitude
        found_location_name = geo_result.name

        # 2. Weather Forecast: Get weather for the coordinates
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
            f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,weather_code"
        )
        try:
            weather_response = await client.get(weather_url)
            weather_response.raise_for_status()
            weather_data = WeatherResponse.model_validate(weather_response.json())
        except httpx.HTTPStatusError as e:
             raise Exception(f"Weather API request failed: {e.response.status_code}") from e
        except Exception as e:
            raise Exception(f"Failed to parse weather response: {e}") from e


        current_weather = weather_data.current

        # 3. Format Output
        output = WeatherOutput(
            temperature=current_weather.temperature_2m,
            feelsLike=current_weather.apparent_temperature,
            humidity=current_weather.relative_humidity_2m,
            windSpeed=current_weather.wind_speed_10m,
            windGust=current_weather.wind_gusts_10m,
            conditions=get_weather_condition(current_weather.weather_code),
            location=found_location_name,
        )
        return output

if __name__ == "__main__":
    mcp.run(transport="stdio")
