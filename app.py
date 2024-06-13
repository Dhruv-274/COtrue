from flask import Flask, request, jsonify, render_template
import subprocess
import os
import tempfile
import time
import requests
import psutil
app = Flask(__name__)

API_KEY = '2dq7FLVxtywZ4'
API_URL = 'https://api.co2signal.com/v1/latest'
LOCATION = 'IN'

def estimate_carbon_emission_api(duration):
    headers = {'auth-token': API_KEY}
    params = {'countryCode': LOCATION}
    
    try:
        response = requests.get(API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        carbon_intensity = data['data']['carbonIntensity']
        duration_hours = duration / 3600
        server_power_kw = 0.2 
        energy_consumption_kwh = server_power_kw * duration_hours
        carbon_emission = energy_consumption_kwh * carbon_intensity / 1000  
        return carbon_emission
    except requests.RequestException as e:
        return f'Error calling the CO2 Signal API: {str(e)}'
    except KeyError:
        return 'Error: Unexpected response structure from CO2 Signal API'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run_code', methods=['POST'])
def run_code():
    data = request.get_json()
    analysis_type = data['type']
    
    if analysis_type == 'system':
        cpu_usage = psutil.cpu_percent(interval=1)
        ram_usage = psutil.virtual_memory().percent
        gpu_usage = None
        
        return jsonify({'cpuUsage': cpu_usage, 'ramUsage': ram_usage, 'gpuUsage': gpu_usage})

    elif analysis_type in ['single', 'compare']:
        language = data['language']
        codes = [data['code']] if analysis_type == 'single' else [data['code1'], data['code2']]
        
        results = []
        for code in codes:
            temp_dir = tempfile.mkdtemp()
            source_file = os.path.join(temp_dir, f'code.{language}')
            
            try:
                with open(source_file, 'w') as f:
                    f.write(code)
                
                start_time = time.time()
                
                if language == 'python':
                    result = subprocess.run(['python', source_file], capture_output=True, text=True)
                elif language == 'c':
                    executable = os.path.join(temp_dir, 'a.out')
                    compile_result = subprocess.run(['gcc', source_file, '-o', executable], capture_output=True, text=True) 
                    if compile_result.returncode != 0:
                        results.append({'error': f'Compilation failed: {compile_result.stderr}'})
                        continue
                    result = subprocess.run([executable], capture_output=True, text=True)
                else:
                    return jsonify({'error': 'Unsupported language'}), 400

                end_time = time.time()
                duration = end_time - start_time
                carbon_emission = estimate_carbon_emission_api(duration)
                
                results.append({'output': result.stdout or result.stderr, 'carbonEmission': carbon_emission})
            except Exception as e:
                results.append({'error': str(e)})
            finally:
                os.remove(source_file)
                if language == 'c':
                    executable = os.path.join(temp_dir, 'a.out')
                    if os.path.exists(executable):
                        os.remove(executable)
                os.rmdir(temp_dir)
        
        if analysis_type == 'single':
            return jsonify(results[0])
        else:
            return jsonify({'code1': results[0], 'code2': results[1]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
