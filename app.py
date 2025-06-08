from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import os
import requests
from datetime import datetime, timedelta
import json

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not API_KEY:
    raise ValueError("No OpenWeatherMap API key found. Please add it to .env file.")

# Tegal coordinates
TEGAL_COORDS = {"lat": -6.8694, "lon": 109.1402}

# Load crop data
with open('data/crops.json', 'r', encoding='utf-8') as f:
    crops = json.load(f)

# Load planting rules
with open('data/planting_rules.json', 'r', encoding='utf-8') as f:
    planting_rules = json.load(f)


# route app

@app.route('/')
def home():
    """Render the home page"""
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    """Render the dashboard page"""
    return render_template('dashboard.html')



# api

@app.route('/api/weather')
def get_weather():
    """Get weather data from OpenWeatherMap API"""
    try:
        # Get current weather
        current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={TEGAL_COORDS['lat']}&lon={TEGAL_COORDS['lon']}&appid={API_KEY}&units=metric&lang=id"
        current_response = requests.get(current_url)
        current_response.raise_for_status()
        current_data = current_response.json()

        # Get forecast data
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={TEGAL_COORDS['lat']}&lon={TEGAL_COORDS['lon']}&appid={API_KEY}&units=metric&lang=id"
        forecast_response = requests.get(forecast_url)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        # Process current weather
        current = {
            "temp": round(current_data["main"]["temp"]),
            "humidity": current_data["main"]["humidity"],
            "windSpeed": round(current_data["wind"]["speed"] * 10) / 10,
            "visibility": round(current_data["visibility"] / 1000),
            "description": current_data["weather"][0]["description"],
            "pressure": current_data["main"]["pressure"]
        }

        # Process forecast data
        forecast = process_forecast_data(forecast_data["list"])

        return jsonify({
            "current": current,
            "forecast": forecast,
            "location": {
                "name": "Tegal",
                "country": "Indonesia",
                "coords": TEGAL_COORDS
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommendation')
def get_recommendation():
    """Get planting recommendation based on weather data and selected crop"""
    try:
        crop_id = request.args.get('crop_id', 'padi')
        
        # Get weather data
        weather_data = get_weather_data()
        
        # Calculate recommendation
        recommendation = calculate_optimal_planting_time(weather_data, crop_id)
        
        return jsonify(recommendation)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/crops')
def get_crops():
    """Get crops data"""
    return jsonify(crops)

def get_weather_data():
    """Helper function to get weather data"""
    try:
        # Get current weather
        current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={TEGAL_COORDS['lat']}&lon={TEGAL_COORDS['lon']}&appid={API_KEY}&units=metric&lang=id"
        current_response = requests.get(current_url)
        current_response.raise_for_status()
        current_data = current_response.json()

        # Get forecast data
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={TEGAL_COORDS['lat']}&lon={TEGAL_COORDS['lon']}&appid={API_KEY}&units=metric&lang=id"
        forecast_response = requests.get(forecast_url)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        # Process current weather
        current = {
            "temp": round(current_data["main"]["temp"]),
            "humidity": current_data["main"]["humidity"],
            "windSpeed": round(current_data["wind"]["speed"] * 10) / 10,
            "visibility": round(current_data["visibility"] / 1000),
            "description": current_data["weather"][0]["description"],
            "pressure": current_data["main"]["pressure"]
        }

        # Process forecast data
        forecast = process_forecast_data(forecast_data["list"])

        return {
            "current": current,
            "forecast": forecast,
            "location": {
                "name": "Tegal",
                "country": "Indonesia",
                "coords": TEGAL_COORDS
            }
        }
    except Exception as e:
        raise Exception(f"Error fetching weather data: {str(e)}")

def process_forecast_data(forecast_list):
    """Process forecast data from OpenWeatherMap API"""
    daily_data = {}

    for item in forecast_list:
        date = datetime.fromtimestamp(item["dt"])
        date_key = date.strftime("%Y-%m-%d")

        if date_key not in daily_data:
            daily_data[date_key] = {
                "date": format_date(date),
                "temps": [],
                "humidity": [],
                "rainfall": 0,
                "windSpeed": []
            }

        daily_data[date_key]["temps"].append(item["main"]["temp"])
        daily_data[date_key]["humidity"].append(item["main"]["humidity"])
        daily_data[date_key]["windSpeed"].append(item["wind"]["speed"])

        # Calculate rainfall
        if "rain" in item and "3h" in item["rain"]:
            daily_data[date_key]["rainfall"] += item["rain"]["3h"]

    # Convert to array and calculate averages
    result = []
    for date_key, day in daily_data.items():
        result.append({
            "date": day["date"],
            "tempMin": round(min(day["temps"])),
            "tempMax": round(max(day["temps"])),
            "tempAvg": round(sum(day["temps"]) / len(day["temps"])),
            "humidity": round(sum(day["humidity"]) / len(day["humidity"])),
            "rainfall": round(day["rainfall"] * 10) / 10,
            "windSpeed": round((sum(day["windSpeed"]) / len(day["windSpeed"])) * 10) / 10
        })

    return result

def format_date(date):
    """Format date to Indonesian format"""
    days = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    
    day_name = days[date.weekday()]
    day = date.day
    month = months[date.month - 1]
    
    return f"{day_name}, {day} {month}"

def calculate_optimal_planting_time(weather_data, crop_id):
    """Calculate optimal planting time based on weather data and crop"""
    # Find crop and rules
    crop = next((c for c in crops if c["id"] == crop_id), None)
    rules = planting_rules.get(crop_id, None)

    if not crop or not rules or not weather_data.get("forecast"):
        return {
            "status": "unknown",
            "statusText": "Data tidak lengkap",
            "recommendation": "Tidak dapat memberikan rekomendasi",
            "bestDates": [],
            "avgTemp": 0,
            "totalRainfall": 0,
            "avgHumidity": 0
        }

    forecast = weather_data["forecast"][:8]  # 8 days ahead

    # Calculate averages
    avg_temp = round(sum(day["tempAvg"] for day in forecast) / len(forecast))
    total_rainfall = round(sum(day["rainfall"] for day in forecast) * 10) / 10
    avg_humidity = round(sum(day["humidity"] for day in forecast) / len(forecast))

    # Evaluate conditions
    temp_score = evaluate_temperature(avg_temp, rules["temperature"])
    rainfall_score = evaluate_rainfall(total_rainfall, rules["rainfall"])
    humidity_score = evaluate_humidity(avg_humidity, rules["humidity"])

    # Check for avoid conditions
    avoidance_issues = check_avoid_conditions(forecast, rules["avoidConditions"])

    # Calculate overall score
    overall_score = (temp_score + rainfall_score + humidity_score) / 3

    # Determine status
    if avoidance_issues:
        status = "bad"
        status_text = "Tidak Disarankan"
        recommendation = f"Hindari menanam karena: {', '.join(avoidance_issues)}"
    elif overall_score >= 0.8:
        status = "optimal"
        status_text = "Sangat Baik"
        recommendation = f"Kondisi sangat optimal untuk menanam {crop['name']}. Mulai tanam sekarang!"
    elif overall_score >= 0.6:
        status = "good"
        status_text = "Baik"
        recommendation = f"Kondisi baik untuk menanam {crop['name']}. Dapat dimulai dengan persiapan yang baik."
    elif overall_score >= 0.4:
        status = "poor"
        status_text = "Kurang Baik"
        recommendation = f"Kondisi kurang optimal. Pertimbangkan menunda atau siapkan mitigasi risiko."
    else:
        status = "bad"
        status_text = "Buruk"
        recommendation = f"Kondisi tidak mendukung. Disarankan menunda penanaman."

    # Find best planting dates
    best_dates = find_best_planting_dates(forecast, rules)

    # If status is bad, empty best dates
    if status == "bad":
        best_dates = []

    # Generate notes
    notes = generate_notes(avg_temp, total_rainfall, avg_humidity, rules, crop)

    return {
        "status": status,
        "statusText": status_text,
        "recommendation": recommendation,
        "bestDates": best_dates,
        "avgTemp": avg_temp,
        "totalRainfall": total_rainfall,
        "avgHumidity": avg_humidity,
        "notes": notes,
        "scores": {
            "temperature": temp_score,
            "rainfall": rainfall_score,
            "humidity": humidity_score,
            "overall": overall_score
        }
    }

def evaluate_temperature(temp, temp_rules):
    """Evaluate temperature conditions"""
    if temp_rules["optimal"]["min"] <= temp <= temp_rules["optimal"]["max"]:
        return 1.0
    elif temp_rules["acceptable"]["min"] <= temp <= temp_rules["acceptable"]["max"]:
        return 0.6
    else:
        return 0.2

def evaluate_rainfall(rainfall, rainfall_rules):
    """Evaluate rainfall conditions"""
    if rainfall_rules["optimal"]["min"] <= rainfall <= rainfall_rules["optimal"]["max"]:
        return 1.0
    elif rainfall_rules["acceptable"]["min"] <= rainfall <= rainfall_rules["acceptable"]["max"]:
        return 0.6
    else:
        return 0.2

def evaluate_humidity(humidity, humidity_rules):
    """Evaluate humidity conditions"""
    if humidity_rules["optimal"]["min"] <= humidity <= humidity_rules["optimal"]["max"]:
        return 1.0
    elif humidity_rules["acceptable"]["min"] <= humidity <= humidity_rules["acceptable"]["max"]:
        return 0.6
    else:
        return 0.2

def check_avoid_conditions(forecast, avoid_rules):
    """Check for conditions to avoid"""
    issues = []

    # Check for consecutive dry days
    consecutive_dry_days = 0
    max_consecutive_dry = 0

    for day in forecast:
        if day["rainfall"] < 1:
            consecutive_dry_days += 1
            max_consecutive_dry = max(max_consecutive_dry, consecutive_dry_days)
        else:
            consecutive_dry_days = 0

    if max_consecutive_dry > avoid_rules["maxConsecutiveDryDays"]:
        issues.append(f"{max_consecutive_dry} hari berturut-turut tanpa hujan")

    # Check for excessive daily rainfall
    max_daily_rain = max(day["rainfall"] for day in forecast)
    if max_daily_rain > avoid_rules["maxDailyRainfall"]:
        issues.append(f"hujan terlalu deras ({max_daily_rain}mm/hari)")

    # Check for minimum temperature
    min_temp = min(day["tempMin"] for day in forecast)
    if min_temp < avoid_rules["minTemperature"]:
        issues.append(f"suhu terlalu rendah ({min_temp}°C)")

    return issues

def find_best_planting_dates(forecast, rules):
    """Find best dates for planting"""
    best_dates = []

    for day in forecast:
        temp_ok = (rules["temperature"]["acceptable"]["min"] <= day["tempAvg"] <= 
                  rules["temperature"]["acceptable"]["max"])
        rain_ok = (1 <= day["rainfall"] <= rules["avoidConditions"]["maxDailyRainfall"])
        humidity_ok = (rules["humidity"]["acceptable"]["min"] <= day["humidity"] <= 
                      rules["humidity"]["acceptable"]["max"])

        if temp_ok and rain_ok and humidity_ok:
            best_dates.append(day["date"])

    return best_dates[:3]  # Maximum 3 best dates

def generate_notes(temp, rainfall, humidity, rules, crop):
    """Generate additional notes based on conditions"""
    notes = []

    if temp < rules["temperature"]["optimal"]["min"]:
        notes.append(f"Suhu sedikit rendah untuk {crop['name']}")
    elif temp > rules["temperature"]["optimal"]["max"]:
        notes.append(f"Suhu sedikit tinggi untuk {crop['name']}")

    if rainfall < rules["rainfall"]["optimal"]["min"]:
        notes.append("Persiapkan sistem irigasi tambahan")
    elif rainfall > rules["rainfall"]["optimal"]["max"]:
        notes.append("Pastikan drainase yang baik")

    if humidity < rules["humidity"]["optimal"]["min"]:
        notes.append("Kelembaban rendah, pertimbangkan mulsa")
    elif humidity > rules["humidity"]["optimal"]["max"]:
        notes.append("Kelembaban tinggi, waspadai penyakit jamur")

    return ". ".join(notes)

if __name__ == '__main__':
    app.run(debug=True)