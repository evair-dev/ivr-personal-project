from tests.fixtures.step_trees.ingress import ingress_step_tree
from tests.fixtures.step_trees.main_menu import main_menu_step_tree
from tests.fixtures.step_trees.make_payment import make_payment_step_tree
from tests.fixtures.step_trees.secure_call import secure_call_step_tree
from tests.fixtures.step_trees.self_service_menu import self_service_step_tree
from tests.fixtures.step_trees.loan_origination import loan_origination_step_tree
from step_trees.shared.ivr.telco_customer_lookup import ivr_telco_customer_lookup
from step_trees.Iivr.ivr.activate_card import activate_card_step_tree
from step_trees.shared.ivr.customer_lookup import ivr_customer_lookup
from step_trees.Iivr.sms.make_payment_sms import make_payment_sms_step_tree
from step_trees.shared.ivr.noop_queue_transfer import noop_queue_transfer_step_tree
from step_trees.shared.ivr.banking_menu import banking_menu_step_tree

workflow_step_tree_registry = {
    "Iivr.ingress": ingress_step_tree,
    "Iivr.main_menu": main_menu_step_tree,
    "Iivr.secure_call": secure_call_step_tree,
    "Iivr.self_service_menu": self_service_step_tree,
    "Iivr.make_payment": make_payment_step_tree,
    "Iivr.loan_origination": loan_origination_step_tree,
    "Iivr.sms.make_payment_sms": make_payment_sms_step_tree,
    "shared.ivr.noop_queue_transfer": noop_queue_transfer_step_tree,
    "shared.ivr.telco_customer_lookup": ivr_telco_customer_lookup,
    "Iivr.ivr.activate_card": activate_card_step_tree,
    "shared.ivr.customer_lookup": ivr_customer_lookup,
    "shared.ivr.banking_menu": banking_menu_step_tree
}