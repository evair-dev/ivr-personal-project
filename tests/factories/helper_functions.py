from ivr_gateway.models.workflows import WorkflowRun


def compare_step_branches(correct_branch_sequence, workflow_run: WorkflowRun) -> bool:
    ordered_step_runs = [None]*len(workflow_run.workflow_step_runs)
    for workflow_step_run in workflow_run.workflow_step_runs:
        ordered_step_runs[workflow_step_run.run_order] = workflow_step_run

    i = -1
    last_step_branch = None
    num_branches = len(correct_branch_sequence)
    for workflow_step_run in ordered_step_runs:
        if workflow_step_run.step_run.branch != last_step_branch:
            last_step_branch = workflow_step_run.step_run.branch
            i += 1

        assert workflow_step_run.step_run.branch == correct_branch_sequence[i]
    assert i + 1 == num_branches

    return True
