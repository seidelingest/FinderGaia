from astroquery.jplhorizons import Horizons
from datetime import datetime, timedelta

def test_horizons():
    try:
        name = "Ceres"
        today = datetime.utcnow()
        tomorrow = today + timedelta(days=1)
        obj = Horizons(id=name, location='500', epochs={
            'start': today.strftime('%Y-%m-%d %H:%M:%S'),
            'stop': tomorrow.strftime('%Y-%m-%d %H:%M:%S'),
            'step': '1d'}).ephemerides()
        print(obj)
    except Exception as e:
        print(f"Error: {str(e)}")

test_horizons()
