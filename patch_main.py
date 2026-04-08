with open("ed_quant_engine/main.py", "r") as f:
    content = f.read()

new_logic = """
    # Phase 23: Candle-Close Synchronization Scheduling
    schedule.every().hour.at(":01").do(lambda: asyncio.create_task(engine.run_live_cycle()))
    # Phase 8: Daily 08:00 Heartbeat
    schedule.every().day.at("08:00").do(lambda: asyncio.create_task(tg_bot.send_message(engine.get_status_report())))
    # Phase 13: Weekly Tear Sheet Reporting
"""

content = content.replace("    # Phase 23: Candle-Close Synchronization Scheduling\n    schedule.every().hour.at(\":01\").do(lambda: asyncio.create_task(engine.run_live_cycle()))\n    # Phase 13: Weekly Tear Sheet Reporting", new_logic.strip("\n"))

with open("ed_quant_engine/main.py", "w") as f:
    f.write(content)
