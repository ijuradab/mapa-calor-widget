from flask import Flask, render_template, jsonify, send_file, request, Response
import pandas as pd
import folium
from folium import plugins
import json
from datetime import datetime
import io
import locale

# Set locale for Spanish date parsing
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
    except:
        pass  # Use default if Spanish locale not available

import os

app = Flask(__name__)

# Global variable to store the dataframe
df = None
dates_list = []
latam_countries = [
    'Argentina', 'Bolivia', 'Brasil', 'Chile', 'Colombia', 'Costa Rica', 
    'Ecuador', 'El Salvador', 'Guatemala', 'Honduras', 'México', 
    'Paraguay', 'Perú', 'Panamá', 'Uruguay', 'Venezuela', 'REP DOM'
]

def load_data():
    """Load and process the EMBI CSV data"""
    global df, dates_list
    
    try:
        # Try different encodings
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
            raise Exception("Could not load CSV with any encoding")
        
        # Clean column names - remove any extra whitespace
        df.columns = [col.strip() if isinstance(col, str) else col for col in df.columns]
        
        # Custom date parser for Spanish months
        spanish_months = {
            'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'ago': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'
        }
        
        def parse_spanish_date(date_str):
            """Parse dates like '29-oct-07' to datetime"""
            try:
                parts = str(date_str).split('-')
                if len(parts) == 3:
                    day, month_abbr, year = parts
                    month = spanish_months.get(month_abbr.lower(), '01')
                    # Assume 20xx for years 00-30, 19xx for 31-99
                    year_int = int(year)
                    if year_int <= 30:
                        full_year = f"20{year}"
                    else:
                        full_year = f"19{year}"
                    return pd.to_datetime(f"{full_year}-{month}-{day.zfill(2)}")
            except:
                pass
            return pd.NaT
        
        # Convert date column
        df['Fecha'] = df['Fecha'].apply(parse_spanish_date)
        
        # Filter out rows with invalid dates
        df = df.dropna(subset=['Fecha'])
        
        # Sort by date
        df = df.sort_values('Fecha')
        
        # Get list of dates for the slider
        dates_list = df['Fecha'].dt.strftime('%Y-%m-%d').tolist()
        
        # Replace empty strings with NaN for numeric columns
        for country in latam_countries:
            if country in df.columns:
                df[country] = pd.to_numeric(df[country].astype(str).str.replace(',', '.'), errors='coerce')
        
        print(f"Data loaded successfully: {len(df)} rows, {len(dates_list)} dates")
        return True
    except Exception as e:
        print(f"Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return False

# Country coordinates for labels
country_coords = {
    'Argentina': [-34.6, -58.4],
    'Bolivia': [-16.3, -64.9],
    'Brasil': [-14.2, -51.9],
    'Chile': [-35.7, -71.5],
    'Colombia': [4.6, -74.1],
    'Costa Rica': [9.7, -83.8],
    'Ecuador': [-1.8, -78.1],
    'El Salvador': [13.7, -88.9],
    'Guatemala': [15.8, -90.2],
    'Honduras': [15.2, -86.2],
    'México': [23.6, -102.6],
    'Paraguay': [-23.4, -58.4],
    'Perú': [-9.2, -75.0],
    'Panamá': [8.5, -80.8],
    'Uruguay': [-32.5, -55.8],
    'Venezuela': [6.4, -66.6],
    'REP DOM': [18.7, -70.2]
}

# Advanced label positioning in the ocean to prevent overlap and click blocking
label_positions = {
    'Argentina': [-40.0, -40.0],
    'Bolivia': [-18.0, -92.0],
    'Brasil': [-10.0, -25.0],
    'Chile': [-45.0, -85.0],
    'Colombia': [2.0, -95.0],
    'Costa Rica': [5.0, -98.0],
    'Ecuador': [-4.0, -98.0],
    'El Salvador': [9.0, -102.0],
    'Guatemala': [13.0, -105.0],
    'Honduras': [18.0, -105.0],
    'México': [20.0, -120.0],
    'Paraguay': [-25.0, -35.0],
    'Perú': [-14.0, -95.0],
    'Panamá': [2.0, -85.0],
    'Uruguay': [-35.0, -35.0],
    'Venezuela': [18.0, -65.0],
    'REP DOM': [25.0, -70.0],
}

def get_color_for_value_simple(value, q33, q67):
    """Return color based on value and thresholds"""
    if pd.isna(value):
        return '#cccccc'  # Gray for missing data
    elif value < q33:
        return '#2ecc71'  # Green
    elif value < q67:
        return '#f39c12'  # Yellow/Orange
    else:
        return '#e74c3c'  # Red

def create_map_for_date(date_str):
    """Create a Folium map for a specific date using GeoJson choropleth"""
    try:
        print(f"Creating choropleth map for date: {date_str}")
        
        # Get data for the specific date
        date_obj = pd.to_datetime(date_str)
        row = df[df['Fecha'] == date_obj]
        
        if row.empty:
            print(f"No data found for date: {date_str}")
            return "<html><body><h2>No data available for this date</h2></body></html>"
        
        row = row.iloc[0]
        
        # Prepare data for mapping
        country_values = {}
        data_values = []
        
        for country in latam_countries:
            if country in df.columns:
                value = row[country]
                country_values[country] = value
                if pd.notna(value):
                    data_values.append(value)
        
        # Calculate thresholds
        if data_values:
            q33 = pd.Series(data_values).quantile(0.33)
            q67 = pd.Series(data_values).quantile(0.67)
        else:
            q33, q67 = 2.0, 4.0
        
        # Create base map focused on Latin America
        m = folium.Map(
            location=[10, -75],
            zoom_start=3,
            tiles='OpenStreetMap',
            min_zoom=3
        )
        
        # Map boundaries to restrict view to Latin America
        m.fit_bounds([[25, -115], [-55, -35]])
        
        # Country names mapping between CSV and GeoJSON
        name_mapping = {
            'Argentina': ['Argentina'],
            'Bolivia': ['Bolivia'],
            'Brasil': ['Brazil'],
            'Chile': ['Chile'],
            'Colombia': ['Colombia'],
            'Costa Rica': ['Costa Rica'],
            'Ecuador': ['Ecuador'],
            'El Salvador': ['El Salvador'],
            'Guatemala': ['Guatemala'],
            'Honduras': ['Honduras'],
            'México': ['Mexico'],
            'Paraguay': ['Paraguay'],
            'Perú': ['Peru'],
            'Panamá': ['Panama'],
            'Uruguay': ['Uruguay'],
            'Venezuela': ['Venezuela'],
            'REP DOM': ['Dominican Republic']
        }
        
        # Mapping from GeoJSON name to CSV country name
        geo_to_csv = {}
        for csv_name, geo_names in name_mapping.items():
            for gn in geo_names:
                geo_to_csv[gn] = csv_name

        # GeoJson layer
        geojson_path = 'countries.geojson'
        if os.path.exists(geojson_path):
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
        else:
            geojson_data = 'https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson'
        
        def style_function(feature):
            admin_name = feature['properties'].get('name', '')
            csv_name = geo_to_csv.get(admin_name)
            
            fill_color = '#f0f0f0' 
            if csv_name and csv_name in country_values:
                val = country_values[csv_name]
                fill_color = get_color_for_value_simple(val, q33, q67)
            
            return {
                'fillColor': fill_color,
                'color': 'black',
                'weight': 1.5,
                'fillOpacity': 0.7 if csv_name else 0.05
            }

        def highlight_function(feature):
            admin_name = feature['properties'].get('name', '')
            csv_name = geo_to_csv.get(admin_name)
            return {
                'fillColor': '#ffffff',
                'color': 'black',
                'weight': 3,
                'fillOpacity': 0.9 if csv_name else 0.05
            }

        # Add GeoJson to map
        geo_json = folium.GeoJson(
            geojson_data,
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['name'],
                aliases=['País:'],
                localize=True,
                sticky=True
            )
        )
        
        # Custom click listeners via JavaScript
        click_js = """
        function(e) {
            // En Leaflet GeoJSON, e.layer contiene la capa individual (el país)
            var layer = e.layer || e.target;
            if (!layer.feature) return;
            
            console.log("🔍 Propiedades detectadas:", layer.feature.properties);
            var countryName = layer.feature.properties.name || layer.feature.properties.ADMIN || layer.feature.properties.NAME;
            console.log("🖱️ Click detectado en (iframe):", countryName);
            
            try {
                // Notificar al padre usando handleCountryClick si existe
                if (window.parent && typeof window.parent.handleCountryClick === 'function') {
                    window.parent.handleCountryClick(countryName);
                } else if (window.top && typeof window.top.handleCountryClick === 'function') {
                    window.top.handleCountryClick(countryName);
                } else {
                    console.warn("⚠️ No se pudo comunicar con la página principal (handleCountryClick no encontrado)");
                    // Plan C: postMessage
                    window.parent.postMessage({ type: 'country_click', country: countryName }, '*');
                }
            } catch (err) {
                console.error("❌ Error comunicando con el padre:", err);
            }
        }
        """

        # Injecting at the root level to ensure everything is initialized
        injection_js = f"""
        (function() {{
            console.log("🌊 Script de inyección en el mapa iniciado");
            var attempts = 0;
            
            function setupHover() {{
                attempts++;
                var attached = false;
                
                try {{
                    // Buscar capas GeoJSON o grupos en el scope global
                    for (var key in window) {{
                        if (key.startsWith('geo_json_') || key.startsWith('macro_element_') || key === '{geo_json.get_name()}') {{
                            var obj = window[key];
                            if (obj && typeof obj.on === 'function') {{
                                console.log("🎯 Vinculando click a capa global:", key);
                                obj.off('click');
                                obj.on('click', {click_js});
                                attached = true;
                            }}
                        }}
                    }}
                    
                    // Si no se encontró por variable, buscar dentro del mapa
                    if (!attached) {{
                        for (var key in window) {{
                            if (key.startsWith('map_') && window[key] && typeof window[key].eachLayer === 'function') {{
                                var leafletMap = window[key];
                                leafletMap.eachLayer(function(layer) {{
                                    if (layer.feature || (layer.eachLayer && typeof layer.on === 'function')) {{
                                        layer.off('click');
                                        layer.on('click', {click_js});
                                        attached = true;
                                    }}
                                }});
                                break;
                            }}
                        }}
                    }}
                }} catch (e) {{
                    console.error("❌ Error en setupHover:", e);
                }}
                
                if (attached) {{
                    console.log("✅ Click vinculado correctamente");
                }} else if (attempts < 60) {{
                    if (attempts % 10 === 0) console.log("⏳ Buscando capas (intento " + attempts + ")...");
                    setTimeout(setupHover, 300);
                }} else {{
                    console.warn("❌ No se encontró capa para vincular el click");
                }}
            }}
            setupHover();
        }})();
        """
        m.get_root().script.add_child(folium.Element(injection_js))
        
        geo_json.add_to(m)

        # Add permanent value labels with callouts
        for country, base_coords in country_coords.items():
            if country in country_values:
                val = country_values[country]
                if pd.notna(val):
                    display_coords = label_positions.get(country, base_coords)
                    
                    # Draw callout line if position is offset
                    if display_coords != base_coords:
                        folium.PolyLine(
                            locations=[base_coords, display_coords],
                            color='#666666',
                            weight=1,
                            dash_array='5, 5',
                            opacity=0.6
                        ).add_to(m)
                    
                    folium.Marker(
                        location=display_coords,
                        icon=folium.DivIcon(
                            icon_size=(150,36),
                            icon_anchor=(75,18),
                            html=f'<div style="font-size: 10pt; font-weight: bold; color: black; background-color: rgba(255,255,255,0.7); padding: 2px 4px; border-radius: 4px; text-align: center; border: 1px solid #666; width: fit-content; white-space: nowrap; box-shadow: 1px 1px 3px rgba(0,0,0,0.2); pointer-events: none;">{val:.2f}%</div>',
                        )
                    ).add_to(m)
        
        # Add legend
        legend_html = f'''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 220px; height: 160px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <p style="margin: 0 0 10px 0; font-weight: bold; font-size: 16px;">EMBI LATAM (%)</p>
            <p style="margin: 5px 0;"><span style="background-color: #2ecc71; padding: 3px 10px; border-radius: 3px; color: white;">■</span> Bajo (&lt; {q33:.2f}%)</p>
            <p style="margin: 5px 0;"><span style="background-color: #f39c12; padding: 3px 10px; border-radius: 3px; color: white;">■</span> Medio ({q33:.2f}% - {q67:.2f}%)</p>
            <p style="margin: 5px 0;"><span style="background-color: #e74c3c; padding: 3px 10px; border-radius: 3px; color: white;">■</span> Alto (&gt; {q67:.2f}%)</p>
            <p style="margin: 10px 0 0 0; font-size: 11px; color: #666; border-top: 1px solid #eee; padding-top: 8px;">📅 {date_str}</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        print("Latin America Choropleth map with labels generated successfully")
        return m._repr_html_()
    
    except Exception as e:
        print(f"Error creating map: {e}")
        import traceback
        traceback.print_exc()
        return f"<html><body><h2>Error generating map</h2><p>{str(e)}</p></body></html>"

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/dates')
def get_dates():
    """Return list of available dates"""
    return jsonify({
        'dates': dates_list,
        'count': len(dates_list)
    })

@app.route('/api/map/<date>')
def get_map(date):
    """Return map HTML for a specific date"""
    map_html = create_map_for_date(date)
    return Response(map_html, mimetype='text/html')

@app.route('/api/debug/map/<date>')
def debug_map(date):
    """Debug map generation"""
    try:
        map_html = create_map_for_date(date)
        return map_html
    except Exception as e:
        return f"<h1>Debug Error</h1><pre>{str(e)}</pre>"

@app.route('/api/historical/<country>')
def get_historical_data(country):
    """Return historical EMBI data for a specific country"""
    try:
        if country not in df.columns:
            # Try to handle mapping if needed
            csv_name = None
            # The name_mapping from create_map_for_date is local, 
            # ideally we should have a shared mapping or verify against latam_countries
            if country in latam_countries:
                csv_name = country
            else:
                # Reverse lookup in name_mapping logic (simplified)
                name_mapping = {
                    'Brazil': 'Brasil', 'Mexico': 'México', 'Peru': 'Perú', 
                    'Panama': 'Panamá', 'Dominican Republic': 'REP DOM'
                }
                csv_name = name_mapping.get(country, country)

            if csv_name not in df.columns:
                return jsonify({'error': f'Country {country} not found'}), 404
            country = csv_name

        historical = df[['Fecha', country]].dropna()
        data = {
            'labels': historical['Fecha'].dt.strftime('%Y-%m-%d').tolist(),
            'values': historical[country].tolist()
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/country/<country>/<date>')
def download_country_date(country, date):
    """Download CSV for a specific country and date"""
    try:
        date_obj = pd.to_datetime(date)
        row = df[df['Fecha'] == date_obj]
        
        if row.empty or country not in df.columns:
            return "Data not found", 404
        
        # Create CSV with country data
        export_data = pd.DataFrame({
            'Fecha': [date],
            'País': [country],
            'EMBI': [row.iloc[0][country]]
        })
        
        # Convert to CSV
        output = io.StringIO()
        export_data.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'EMBI_{country}_{date}.csv'
        )
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/api/download/all/<date>')
def download_all_date(date):
    """Download CSV for all countries on a specific date"""
    try:
        date_obj = pd.to_datetime(date)
        row = df[df['Fecha'] == date_obj]
        
        if row.empty:
            return "Data not found", 404
        
        # Create CSV with all Latin American countries
        export_data = []
        for country in latam_countries:
            if country in df.columns:
                export_data.append({
                    'Fecha': date,
                    'País': country,
                    'EMBI': row.iloc[0][country]
                })
        
        export_df = pd.DataFrame(export_data)
        
        # Convert to CSV
        output = io.StringIO()
        export_df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'EMBI_Todos_{date}.csv'
        )
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/api/download/range/<country>/<start_date>/<end_date>')
def download_range(country, start_date, end_date):
    """Download CSV for a country within a date range"""
    try:
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        # Filter data
        mask = (df['Fecha'] >= start) & (df['Fecha'] <= end)
        filtered_df = df[mask]
        
        if filtered_df.empty or country not in df.columns:
            return "Data not found", 404
        
        # Create export data
        export_data = pd.DataFrame({
            'Fecha': filtered_df['Fecha'].dt.strftime('%Y-%m-%d'),
            'País': country,
            'EMBI': filtered_df[country]
        })
        
        # Convert to CSV
        output = io.StringIO()
        export_data.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'EMBI_{country}_{start_date}_to_{end_date}.csv'
        )
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/api/download/range/all/<start_date>/<end_date>')
def download_range_all(start_date, end_date):
    """Download CSV for all countries within a date range"""
    try:
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        # Filter data
        mask = (df['Fecha'] >= start) & (df['Fecha'] <= end)
        filtered_df = df[mask]
        
        if filtered_df.empty:
            return "Data not found", 404
        
        # Create export data with all countries
        export_data = []
        for _, row in filtered_df.iterrows():
            for country in latam_countries:
                if country in df.columns:
                    export_data.append({
                        'Fecha': row['Fecha'].strftime('%Y-%m-%d'),
                        'País': country,
                        'EMBI': row[country]
                    })
        
        export_df = pd.DataFrame(export_data)
        
        # Convert to CSV
        output = io.StringIO()
        export_df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'EMBI_Todos_{start_date}_to_{end_date}.csv'
        )
    except Exception as e:
        return f"Error: {e}", 500

# Load data when the module is imported (essential for Gunicorn)
print("Loading EMBI data...")
if not load_data():
    print("Warning: Failed to load data. Please check the CSV file.")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Server starting on port {port} with {len(dates_list)} dates available")
    if dates_list:
        print(f"Date range: {dates_list[0]} to {dates_list[-1]}")
    app.run(debug=True, host='0.0.0.0', port=port)
