import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from planka_tools.api.client import PlankaClient
from planka_tools.jobs.Scheduled import move_this_month_to_this_week as job

with PlankaClient() as client:
    job.run(client)
