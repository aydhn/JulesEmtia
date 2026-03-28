import pandas as pd
import matplotlib.pyplot as plt
from core.paper_db import db

def generate_tear_sheet(output_file="report.html"):
    trades = db.get_open_trades() # In real implementation, get closed trades

    html_content = """
    <html>
    <head><title>ED Capital - Piyasalara Genel Bakış</title></head>
    <style>body { font-family: Arial, sans-serif; background-color: #f4f4f9; color: #333; } h1 { color: #004080; }</style>
    <body>
    <h1>ED Capital - Piyasalara Genel Bakış</h1>
    <p>Algoritmik işlem performans raporu.</p>
    """

    with open(output_file, "w") as f:
        f.write(html_content + "</body></html>")

    return output_file
