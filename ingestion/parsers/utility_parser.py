"""
Utility Portal CSV Parser.

WHY CSV: Most utility portals (Enel, EDF, National Grid, BESCOM, etc.)
offer a "Download Usage Data" button that produces CSV. PDF bills exist
but require OCR which is brittle. APIs (Green Button API, ESPI standard)
exist but require utility-side enrollment that 80% of enterprise clients
haven't done. CSV download is the common denominator.

Expected format (Green Button-inspired but simplified):
  meter_id, meter_name, service_address,
  billing_period_start, billing_period_end,
  consumption_kwh, demand_kw, tariff_code,
  amount_currency, currency, unit

Key challenge: billing periods don't align with calendar months.
We store billing periods as-is and let the analyst decide how to
allocate across months.
"""

import pandas as pd
import io
from decimal import Decimal
from datetime import datetime

UNIT_CONVERSION_TO_KWH = {
    'kwh': Decimal('1'),
    'mwh': Decimal('1000'),
    'gj':  Decimal('277.778'),
    'mj':  Decimal('0.27778'),
    'kj':  Decimal('0.000278'),
    'therm': Decimal('29.3071'),
}


def parse_utility_csv(file_content: bytes) -> dict:
    records = []
    errors = []

    for encoding in ['utf-8', 'utf-8-sig', 'latin-1']:
        try:
            text = file_content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    df = pd.read_csv(io.StringIO(text), dtype=str)
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
    metadata = {'original_columns': list(df.columns), 'row_count': len(df)}

    # Flexible column matching
    col_aliases = {
        'meter_id':              ['meter_id', 'meterid', 'meter_number', 'mpan', 'account_number'],
        'billing_period_start':  ['billing_period_start', 'start_date', 'period_start', 'from_date', 'read_from'],
        'billing_period_end':    ['billing_period_end', 'end_date', 'period_end', 'to_date', 'read_to'],
        'consumption':           ['consumption_kwh', 'consumption', 'usage', 'kwh', 'units_consumed', 'energy_kwh'],
        'unit':                  ['unit', 'units', 'uom', 'consumption_unit'],
        'service_address':       ['service_address', 'address', 'site', 'location', 'facility'],
    }
    mapped = {}
    for field, aliases in col_aliases.items():
        for alias in aliases:
            if alias in df.columns:
                mapped[field] = alias
                break

    if 'consumption' not in mapped:
        return {
            'records': [],
            'errors': ['Cannot find consumption column. Expected one of: consumption_kwh, usage, kwh'],
            'metadata': metadata,
        }

    for idx, row in df.iterrows():
        try:
            # Dates
            start_str = str(row.get(mapped.get('billing_period_start', ''), '')).strip()
            end_str   = str(row.get(mapped.get('billing_period_end', ''), '')).strip()
            start_date = _parse_date(start_str)
            end_date   = _parse_date(end_str)
            activity_date = start_date or end_date
            if not activity_date:
                errors.append({'row': idx, 'error': 'No parseable date', 'raw': dict(row)})
                continue

            # Consumption
            raw_qty = str(row[mapped['consumption']]).replace(',', '').strip()
            quantity = Decimal(raw_qty)

            # Unit detection
            raw_unit = 'kwh'  # default assumption
            if 'unit' in mapped:
                raw_unit = str(row[mapped['unit']]).strip().lower()

            # Convert to kWh
            conversion = UNIT_CONVERSION_TO_KWH.get(raw_unit, None)
            quantity_kwh = quantity * conversion if conversion else None

            flag = ''
            status = 'PENDING'
            if not conversion:
                flag = f'Unknown unit: {raw_unit} — kWh conversion skipped'
                status = 'FLAGGED'

            # Multi-month billing period detection
            billing_days = None
            if start_date and end_date:
                from datetime import date as dt
                start_d = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_d   = datetime.strptime(end_date,   '%Y-%m-%d').date()
                billing_days = (end_d - start_d).days
                if billing_days > 35:
                    flag += f' | Billing period is {billing_days} days (>1 month) — may need proration'
                    status = 'FLAGGED'

            record = {
                'activity_date': activity_date,
                'activity_description': f"Electricity — {row.get(mapped.get('service_address', ''), 'Unknown site')}",
                'raw_quantity': quantity,
                'raw_unit': raw_unit,
                'quantity_kwh': quantity_kwh,
                'raw_source_row': dict(row),
                'source_location': str(row.get(mapped.get('meter_id', ''), '')).strip(),
                'source_entity': str(row.get(mapped.get('service_address', ''), '')).strip(),
                'scope': 2,
                'category': 'ELECTRICITY',
                'flag_reason': flag.strip(' |'),
                'status': status,
            }
            records.append(record)

        except Exception as e:
            errors.append({'row': idx, 'error': str(e), 'raw': dict(row)})

    return {'records': records, 'errors': errors, 'metadata': metadata}


def _parse_date(raw: str) -> str | None:
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d %b %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None
