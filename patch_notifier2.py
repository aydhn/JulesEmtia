import re

with open("ed_quant_engine/src/notifier.py", "r") as f:
    content = f.read()

# Fix indentation which was lost in regex replacement
content = content.replace("async def send_message", "    async def send_message")
content = content.replace("async def send_document", "    async def send_document")

with open("ed_quant_engine/src/notifier.py", "w") as f:
    f.write(content)
