import pandas as pd

# Try loading the CSV
encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
df = None

for encoding in encodings:
    try:
        df = pd.read_csv('Serie_Historica_Spread_del_EMBI(Serie Histórica).csv', 
                        skiprows=1, sep=';', encoding=encoding)
        print(f"Successfully loaded with encoding: {encoding}")
        break
    except UnicodeDecodeError:
        continue

if df is None:
    print("Could not load CSV")
    exit(1)

# Clean column names
df.columns = df.columns.str.strip()
print(f"\nColumns: {df.columns.tolist()}")

# Convert date column
df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d-%b-%y', errors='coerce')
df = df.dropna(subset=['Fecha'])
df = df.sort_values('Fecha')

print(f"\nFirst date: {df['Fecha'].iloc[0]}")
print(f"Last date: {df['Fecha'].iloc[-1]}")
print(f"Total rows: {len(df)}")

# Check first row
print(f"\nFirst row data:")
first_row = df.iloc[0]
print(f"Date: {first_row['Fecha']}")

south_american_countries = ['Argentina', 'Bolivia', 'Brasil', 'Chile', 'Colombia', 
                            'Ecuador', 'Paraguay', 'Perú', 'Uruguay', 'Venezuela']

for country in south_american_countries:
    if country in df.columns:
        value = first_row[country]
        print(f"{country}: {value}")
