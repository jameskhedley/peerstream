from flask import Flask
import time
app = Flask(__name__)

@app.route('/')
def hello():
    time.sleep(5)
    return 'Hello, World!'

app.run(host='0.0.0.0',port=5000, debug=False, processes=1)
