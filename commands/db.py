import os
import sys

import click
import json

from commands.base import DbCommandBase
from ivr_gateway.models.admin import AdminCall, ScheduledCall, AdminCallFrom, AdminCallTo
from ivr_gateway.models.contacts import Contact, TransferRouting, InboundRouting, Greeting, ContactLeg
from ivr_gateway.models.queues import Queue, QueueHoursOfOperation, QueueHoliday
from ivr_gateway.models.workflows import WorkflowRun, Workflow, WorkflowConfig
from ivr_gateway.services.workflows import WorkflowService


class Db(DbCommandBase):

    @property
    def workflow_service(self):
        return WorkflowService(self.db_session)

    @click.command()
    def clear_workflow_runs(self):
        """Clear DB"""
        if os.getenv("IVR_APP_ENV") not in ["local", "dev", "test"]:
            click.echo("Exiting because command cannot be run in production mode")
            sys.exit(1)
        for wr in self.db_session.query(WorkflowRun).all():
            step_runs = {}
            for wsr in wr.workflow_step_runs:
                if wsr.step_run.id not in step_runs:
                    step_runs[wsr.step_run.id] = wsr.step_run
                self.db_session.delete(wsr)
            for _, sr in step_runs.items():
                self.db_session.delete(sr)
            self.db_session.delete(wr)
            self.db_session.flush()
        self.db_session.commit()

        click.echo("Runs Cleared.")

    @click.command()
    def clear_call_inbound_transfer_and_admin_data(self):
        """Clear DB"""
        if os.getenv("IVR_APP_ENV") not in ["local", "dev", "test"]:
            click.echo("Exiting because command cannot be run in production mode")
            sys.exit(1)

        self.db_session.query(ContactLeg).delete()
        self.db_session.query(Contact).delete()
        self.db_session.query(AdminCall).delete()
        self.db_session.query(ScheduledCall).delete()
        self.db_session.query(TransferRouting).delete()
        self.db_session.query(InboundRouting).delete()
        self.db_session.query(Greeting).delete()
        self.db_session.query(WorkflowConfig).delete()
        self.db_session.query(Workflow).delete()


        self.db_session.commit()
        click.echo("Data Cleared.")


    @click.command()
    def clear_queues(self):
        """Clear Queues"""

        if os.getenv("IVR_APP_ENV") not in ["local", "dev", "test"]:
            click.echo("Exiting because command cannot be run in production mode")
            sys.exit(1)

        self.db_session.query(QueueHoursOfOperation).delete()
        self.db_session.query(QueueHoliday).delete()
        self.db_session.query(Queue).delete()
        click.echo("Queues Cleared.")

    @click.command()
    def clear_admin_shortcuts(self):
        """Clear admin shortcuts"""

        if os.getenv("IVR_APP_ENV") not in ["local", "dev", "test"]:
            click.echo("Exiting because command cannot be run in production mode")
            sys.exit(1)
        self.db_session.query(AdminCallFrom).delete()
        self.db_session.query(AdminCallTo).delete()
        click.echo("Shortcuts cleared.")

    @click.command(help="Look at a call's Workflow")
    @click.option("--phone-number",
                  prompt="What is the phone number that was used to call the IVR?  (e.g. 14432351191)",
                  help="Phone number for the call you want to lookup.",
                  type=click.STRING)
    def peek_workflow(self, phone_number: str) -> None:
        contact_legs_in_db = self.workflow_service.get_contact_legs_by_phone_number(phone_number)

        if contact_legs_in_db:
            click.echo("Call Logs:")
            click.echo('-------------------------------------------------')
            for contact_num, contact_leg in enumerate(contact_legs_in_db):
                click.echo(f"{contact_num + 1} - Created At: {contact_leg.created_at}")
                click.echo(f"From: {contact_leg.ani}")
                click.echo(f"To: {contact_leg.dnis}")
                click.echo('-------------------------------------------------')

            call_to_trace = click.prompt("Which call would you like to trace: ",
                                         type=click.IntRange(1, len(contact_legs_in_db)))
            call_contact_id = contact_legs_in_db[call_to_trace - 1].contact_id
            call_contact_legs = self.workflow_service.get_contact_legs_by_contact_id(call_contact_id)

            click.echo('-------------------------------------------------')
            for contact_num, contact_leg in enumerate(call_contact_legs):
                click.echo(f"{contact_num + 1} - Created At: {contact_leg.created_at}")
                click.echo(f"disposition_kwargs: {contact_leg.disposition_kwargs}")
                click.echo(f"disposition_type: {contact_leg.disposition_type}")
                click.echo('-------------------------------------------------')

            workflow_to_trace = click.prompt("Which call step would you like to focus: ",
                                             type=click.IntRange(1, len(call_contact_legs)))
            workflow_to_trace_id = call_contact_legs[workflow_to_trace - 1].workflow_run_id
            workflow_session_object = (self.workflow_service.get_workflow_run_by_id(workflow_to_trace_id)
                                       .contact_leg.contact.session)
            workflow_steps = self.workflow_service.get_workflow_steps_by_workflow_run_id(workflow_to_trace_id)
            click.echo('-------------------------------------------------')
            for step in workflow_steps:
                click.echo(f"Workflow Name: {step[2]}")
                click.echo(f"Branch: {step[3]}")
                click.echo(f"Step: {step[4]}")
                click.echo(f"Step State Result: {json.dumps(step[7], indent=4, sort_keys=True)}")
                click.echo('-------------------------------------------------')
            click.echo(f"Complete Workflow Session: {workflow_session_object}")

        return


