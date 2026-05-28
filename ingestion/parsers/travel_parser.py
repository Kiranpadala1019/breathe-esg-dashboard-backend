"""
Corporate Travel Parser (Concur/Navan-style CSV export)
"""

import pandas as pd
import io
import math
from decimal import Decimal
from datetime import datetime

AIRPORT_COORDS = {
    'DEL': (28.5665, 77.1031),
    'BOM': (19.0896, 72.8656),
    'BLR': (13.1979, 77.7063),
    'MAA': (12.9941, 80.1709),
    'LHR': (51.4775, -0.4614),
    'CDG': (49.0097, 2.5479),
    'JFK': (40.6413, -73.7781),
    'ORD': (41.9742, -87.9073),
    'SFO': (37.6213, -122.379),
    'LAX': (33.9425, -118.408),
    'DXB': (25.2532, 55.3657),
    'SIN': (1.3644, 103.9915),
    'HKG': (22.3080, 113.9185),
    'NRT': (35.7647, 140.386),
    'SYD': (-33.9461, 151.177),
    'GRU': (-23.4356, -46.4731),
}

EMISSION_FACTORS = {
    'flight_short_haul': Decimal('0.255'),
    'flight_long_haul': Decimal('0.195'),
    'hotel_night': Decimal('31.2'),
    'car': Decimal('0.171'),
    'train': Decimal('0.041'),
    'taxi': Decimal('0.171'),
}

EXPENSE_TYPE_MAP = {
    'airfare': 'TRAVEL_AIR',
    'air': 'TRAVEL_AIR',
    'flight': 'TRAVEL_AIR',
    'hotel': 'TRAVEL_HOTEL',
    'lodging': 'TRAVEL_HOTEL',
    'accommodation': 'TRAVEL_HOTEL',
    'car rental': 'TRAVEL_GROUND',
    'rental car': 'TRAVEL_GROUND',
    'taxi': 'TRAVEL_GROUND',
    'rideshare': 'TRAVEL_GROUND',
    'uber': 'TRAVEL_GROUND',
    'train': 'TRAVEL_GROUND',
    'rail': 'TRAVEL_GROUND',
    'ground transport': 'TRAVEL_GROUND',
}


def parse_travel_csv(file_content: bytes) -> dict:
    records = []
    errors = []

    # Decode file
    text = None
    for encoding in ['utf-8', 'utf-8-sig', 'latin-1']:
        try:
            text = file_content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        return {
            'records': [],
            'errors': [{'row': 0, 'error': 'Could not decode file'}],
            'metadata': {}
        }

    # Flexible CSV parser
    try:
        df = pd.read_csv(
            io.StringIO(text),
            dtype=str,
            sep=None,
            engine="python",
            on_bad_lines="skip"
        )
    except Exception as e:
        return {
            'records': [],
            'errors': [{'row': 0, 'error': f'CSV read failed: {str(e)}'}],
            'metadata': {}
        }

    # Clean column names
    df.columns = [
        c.strip().lower().replace(' ', '_')
        for c in df.columns
    ]

    metadata = {
        'original_columns': list(df.columns),
        'row_count': len(df)
    }

    for idx, row in df.iterrows():
        try:

            # Parse date
            activity_date = None
            for col in [
                'transaction_date',
                'date',
                'travel_date',
                'expense_date'
            ]:
                if col in row.index:
                    value = str(row[col]).strip()
                    if value and value != 'nan':
                        activity_date = _parse_date(value)
                        break

            if not activity_date:
                errors.append({
                    'row': idx,
                    'error': 'No valid date'
                })
                continue

            expense_raw = str(
                row.get(
                    'expense_type',
                    row.get('category', '')
                )
            ).strip().lower()

            category = 'TRAVEL_GROUND'

            for key, value in EXPENSE_TYPE_MAP.items():
                if key in expense_raw:
                    category = value
                    break

            description = str(
                row.get(
                    'merchant_name',
                    expense_raw
                )
            ).strip()

            co2e_kg = None
            raw_quantity = Decimal('0')
            raw_unit = ''
            flag = ''
            status = 'PENDING'

            # AIR
            if category == 'TRAVEL_AIR':

                from_code = str(
                    row.get('from_airport', '')
                ).upper().strip()

                to_code = str(
                    row.get('to_airport', '')
                ).upper().strip()

                distance = _airport_distance(
                    from_code,
                    to_code
                )

                if distance:
                    ef = (
                        EMISSION_FACTORS['flight_long_haul']
                        if distance >= 3700
                        else EMISSION_FACTORS['flight_short_haul']
                    )

                    co2e_kg = Decimal(str(distance)) * ef
                    raw_quantity = Decimal(str(distance))
                    raw_unit = 'km'

                    description = (
                        f"Flight {from_code}→{to_code}"
                    )
                else:
                    flag = 'Airport distance unknown'
                    status = 'FLAGGED'

            # HOTEL
            elif category == 'TRAVEL_HOTEL':

                nights = str(
                    row.get(
                        'hotel_nights',
                        row.get('nights', '1')
                    )
                ).strip()

                try:
                    nights = Decimal(nights)
                except:
                    nights = Decimal('1')

                co2e_kg = (
                    nights *
                    EMISSION_FACTORS['hotel_night']
                )

                raw_quantity = nights
                raw_unit = 'nights'

                description = (
                    f"Hotel - "
                    f"{row.get('hotel_city', 'Unknown')}"
                )

            # GROUND
            else:

                dist = str(
                    row.get(
                        'distance_km',
                        row.get('distance', '')
                    )
                ).strip()

                if dist and dist != 'nan':
                    try:
                        distance = float(dist)

                        co2e_kg = (
                            Decimal(str(distance))
                            *
                            EMISSION_FACTORS['car']
                        )

                        raw_quantity = Decimal(
                            str(distance)
                        )

                        raw_unit = 'km'

                    except:
                        flag = 'Invalid distance'
                        status = 'FLAGGED'
                else:
                    flag = 'Distance missing'
                    status = 'FLAGGED'

            records.append({
                'activity_date': activity_date,
                'activity_description': description,
                'raw_quantity': raw_quantity,
                'raw_unit': raw_unit,
                'co2e_kg': co2e_kg,
                'emission_factor_used': 'DEFRA 2023',
                'emission_factor_source': 'DEFRA 2023',

                # FIXED JSON STORAGE
                'raw_source_row': {
                    str(k): (
                        None if pd.isna(v)
                        else str(v)
                    )
                    for k, v in row.items()
                },

                'scope': 3,
                'category': category,
                'flag_reason': flag,
                'status': status,
            })

        except Exception as e:
            errors.append({
                'row': idx,
                'error': str(e)
            })

    return {
        'records': records,
        'errors': errors,
        'metadata': metadata
    }


def _airport_distance(iata1, iata2):

    if (
        iata1 not in AIRPORT_COORDS
        or
        iata2 not in AIRPORT_COORDS
    ):
        return None

    lat1, lon1 = AIRPORT_COORDS[iata1]
    lat2, lon2 = AIRPORT_COORDS[iata2]

    R = 6371

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(math.radians(lat1))
        *
        math.cos(math.radians(lat2))
        *
        math.sin(dlon / 2) ** 2
    )

    return round(
        R * 2 * math.asin(math.sqrt(a)),
        1
    )


def _parse_date(raw):

    formats = [
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%d-%m-%Y',
        '%Y/%m/%d'
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                raw,
                fmt
            ).strftime('%Y-%m-%d')
        except:
            continue

    return None