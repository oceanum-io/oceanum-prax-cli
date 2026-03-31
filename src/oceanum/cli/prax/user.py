import os
from datetime import datetime

import click
import plotext as plt
import yaml

from oceanum.cli.auth import login_required
from oceanum.cli.renderer import Renderer, RenderField
from oceanum.cli.symbols import chk, err, wrn

from . import models
from .client import PRAXClient
from .main import create, describe, usage
from .utils import echoerr


def _format_usage_metric_name(metric_name: str) -> str:
    return metric_name.replace("_", " ").title()


def _format_usage_total(metric_name: str, value: int | float | None) -> str:
    if value is None:
        return "-"
    if metric_name == "cpu":
        return f"{value / 3600:.2f} core-hours"
    if metric_name in {"memory", "ephemeral_storage", "persistent_storage"}:
        return f"{value / (1024**3) / 3600:.2f} GiB-hours"
    if metric_name == "gpu":
        return f"{value / 3600:.2f} gpu-hours"
    return str(value)


def _format_latest_series_value(
    metric_name: str, value: int | float | str | None
) -> str:
    if value in (None, "-"):
        return "-"
    if not isinstance(value, (int, float)):
        return str(value)
    if metric_name.startswith("cpu_"):
        return f"{value:.2f} cores"
    if "memory" in metric_name or "storage" in metric_name:
        return f"{value / (1024**3):.2f} GiB"
    if metric_name.startswith("gpu_"):
        return f"{value:.2f} gpus"
    return f"{value:.2f}"


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_range_label(value: str | None) -> str:
    dt = _parse_timestamp(value)
    if dt is None:
        return value or "-"
    return dt.strftime("%Y-%m-%d %H:%M %Z").strip()


def _format_axis_label(value: str | None, compact: bool = False) -> str:
    dt = _parse_timestamp(value)
    if dt is None:
        return value or "-"
    return dt.strftime("%Y-%m-%d" if compact else "%Y-%m-%d %H:%M")


def _resample_series(values: list[float], width: int) -> list[float]:
    if len(values) <= width:
        return values
    bucket_size = len(values) / width
    buckets = []
    for index in range(width):
        start = int(index * bucket_size)
        end = max(start + 1, int((index + 1) * bucket_size))
        chunk = values[start:end]
        buckets.append(sum(chunk) / len(chunk))
    return buckets


def _plot_series_value(metric_name: str, value: float) -> float:
    if metric_name.startswith("cpu_"):
        return value
    if "memory" in metric_name or "storage" in metric_name:
        return value / (1024**3)
    if metric_name.startswith("gpu_"):
        return value
    return value


def _plot_series_unit(metric_name: str) -> str:
    if metric_name.startswith("cpu_"):
        return "cores"
    if "memory" in metric_name or "storage" in metric_name:
        return "GiB"
    if metric_name.startswith("gpu_"):
        return "gpus"
    return "units"


def _select_plot_metrics(time_series: dict) -> list[str]:
    preferred = [
        "cpu_limits",
        "memory_limits",
        "ephemeral_storage_limits",
        "persistent_storage_limits",
        "gpu_limits",
    ]
    selected = []
    for metric_name in preferred:
        samples = time_series.get(metric_name, [])
        if samples and any(float(sample["value"]) > 0 for sample in samples):
            selected.append(metric_name)
    return selected[:3]


def _should_hide_metric(metric_name: str, values: list[float]) -> bool:
    if metric_name != "ephemeral_storage_limits":
        return False
    average_gib = sum(_plot_series_value(metric_name, value) for value in values) / len(
        values
    )
    return average_gib < 0.1


def _render_usage_plot_block(
    metric_name: str, samples: list[dict], step: str | None = None
) -> str | None:
    if not samples:
        return None

    values = [float(sample["value"]) for sample in samples]
    if not any(value > 0 for value in values):
        return None
    if _should_hide_metric(metric_name, values):
        return None

    sampled_values = _resample_series(values, width=96)
    x_values = list(range(len(sampled_values)))
    plotted_values = [
        _plot_series_value(metric_name, value) for value in sampled_values
    ]
    current = _format_latest_series_value(metric_name, values[-1])
    average = _format_latest_series_value(metric_name, sum(values) / len(values))
    peak = _format_latest_series_value(metric_name, max(values))
    start_label = _format_range_label(samples[0].get("timestamp"))
    end_label = _format_range_label(samples[-1].get("timestamp"))
    compact_axis = len(values) > 96
    axis_start = _format_axis_label(samples[0].get("timestamp"), compact=compact_axis)
    axis_end = _format_axis_label(samples[-1].get("timestamp"), compact=compact_axis)
    resolution_note = (
        f"{len(sampled_values)} cols from {len(values)} {step or ''} samples".strip()
        if len(sampled_values) != len(values)
        else f"{len(values)} cols at native {step or ''} resolution".strip()
    )

    plt.clear_figure()
    plt.plotsize(100, 12)
    plt.theme("pro")
    plt.plot(x_values, plotted_values, marker="dot")
    plt.title(_format_usage_metric_name(metric_name))
    plt.ylabel(_plot_series_unit(metric_name))
    plt.xticks([0, len(x_values) - 1], [axis_start, axis_end])
    plt.xfrequency(2)
    plt.yfrequency(5)
    plot = plt.build()
    plt.clear_figure()

    return os.linesep.join(
        [
            f"current {current}  avg {average}  peak {peak}",
            plot,
            f"{resolution_note}",
        ]
    )


def _render_metric_totals(title: str, totals: dict | None) -> str | None:
    if not totals:
        return None
    total_fields = [
        RenderField(
            label="CPU",
            path="$.cpu",
            mod=lambda value: _format_usage_total("cpu", value),
        ),
        RenderField(
            label="Memory",
            path="$.memory",
            mod=lambda value: _format_usage_total("memory", value),
        ),
        RenderField(
            label="Ephemeral Storage",
            path="$.ephemeral_storage",
            mod=lambda value: _format_usage_total("ephemeral_storage", value),
        ),
        RenderField(
            label="Persistent Storage",
            path="$.persistent_storage",
            mod=lambda value: _format_usage_total("persistent_storage", value),
        ),
        RenderField(
            label="GPU",
            path="$.gpu",
            mod=lambda value: _format_usage_total("gpu", value),
        ),
    ]
    return os.linesep.join(
        [
            title,
            "-" * len(title),
            Renderer(data=[totals], fields=total_fields).render_table(tablefmt="plain"),
        ]
    )


def render_org_usage_summary(usage_data: dict) -> str:
    metadata = usage_data.get("metadata", {})
    time_series = usage_data.get("time_series", {})

    summary_fields = [
        RenderField(label="Organization", path="$.org"),
        RenderField(
            label="Project",
            path="$.project_name",
            mod=lambda value: value or "All projects",
        ),
        RenderField(label="Start", path="$.start_time"),
        RenderField(label="End", path="$.end_time"),
        RenderField(label="Step", path="$.step"),
        RenderField(label="Duration (s)", path="$.duration_seconds"),
        RenderField(label="Data Points", path="$.data_points"),
    ]

    sections = []

    if time_series:
        plot_sections = []
        for metric_name in _select_plot_metrics(time_series):
            plot_section = _render_usage_plot_block(
                metric_name, time_series[metric_name], metadata.get("step")
            )
            if plot_section:
                plot_sections.append(plot_section)

        sections.extend(["Usage", "====="])
        coverage = (
            f"Coverage: {_format_range_label(metadata.get('start_time'))} -> "
            f"{_format_range_label(metadata.get('end_time'))}"
        )
        sections.append(coverage)
        sections.append(
            f"Resolution: {metadata.get('step', '-')}  Samples: {metadata.get('data_points', '-')}"
        )
        if plot_sections:
            sections.extend(["", (os.linesep * 2).join(plot_sections)])
        else:
            sections.extend(
                ["", "No non-zero usage series found in the selected window."]
            )

    if metadata.get("error"):
        sections.extend(
            [
                "",
                click.style("Warning", fg="yellow", bold=True),
                click.style(str(metadata["error"]), fg="yellow"),
            ]
        )

    billing_section = _render_metric_totals(
        "Billing Totals", usage_data.get("billing_totals")
    )
    if billing_section:
        sections.extend(["", billing_section])

    monitoring_section = _render_metric_totals(
        "Monitoring Totals", usage_data.get("monitoring_totals")
    )
    if monitoring_section:
        sections.extend(["", monitoring_section])

    sections.extend(
        [
            "",
            "Summary",
            "=======",
            Renderer(data=[metadata], fields=summary_fields).render_table(
                tablefmt="plain"
            ),
        ]
    )

    return os.linesep.join(sections)


@describe.command(name="user", help="List PRAX Users")
@click.option(
    "--org", help="Organization name to show resources for", default=None, type=str
)
@click.pass_context
@login_required
def describe_user(ctx: click.Context, org: str | None):
    client = PRAXClient(ctx)
    fields = [
        RenderField(label="Username", path="$.username"),
        RenderField(label="Email", path="$.email"),
        RenderField(label="PRAX API Token", path="$.token"),
        RenderField(label="Current Org.", path="$.current_org.name"),
        RenderField(label="Member of Orgs.", path="$.all_orgs.*", sep=os.linesep),
        RenderField(
            label="Deployable Orgs.", path="$.deployable_orgs.*", sep=os.linesep
        ),
        RenderField(label="Admin Orgs.", path="$.admin_orgs.*", sep=os.linesep),
        RenderField(label="Deployed Projects", path="$.projects.*", sep=os.linesep),
        RenderField(
            label="User-Resources:",
            path="$.current_org.resources.*",
            sep=os.linesep,
            mod=lambda x: (
                f"{x['resource_type'].removesuffix('s')}: {x['name']} (keys: {','.join(x['spec']['data'].keys())})"
            ),
        ),
    ]
    users = client.get_users()
    if isinstance(users, list) and org:
        current_org = client.get_org(org)
        if isinstance(current_org, models.ErrorResponse):
            click.echo(f" {err} Error fetching organization '{org}' details:")
            echoerr(current_org)
            return 1
        for user in users:
            user.current_org = current_org
    if isinstance(users, models.ErrorResponse):
        click.echo(f" {err} Error fetching users:")
        echoerr(users)
        return 1
    else:
        click.echo(Renderer(data=users, fields=fields).render_table(tablefmt="plain"))
        user_org = users[0].current_org
        if user_org is not None:
            quotas = list(user_org.tier.model_fields.keys())
            usage = user_org.usage.model_dump()
            tier = user_org.tier.model_dump()
            quota_data = {
                quotas[i]: j for i, j in enumerate(zip(usage.values(), tier.values()))
            }
            mod = lambda x: f"{x[0]} / {x[1]}"
            cpu_fields = [
                RenderField(label="Total CPU (millicores)", path="$.max_cpu", mod=mod),
                RenderField(
                    label="CPU per Service (millicores)",
                    path="$.max_cpu_per_service",
                    mod=mod,
                ),
                RenderField(
                    label="CPU per Task (millicores)",
                    path="$.max_cpu_per_task",
                    mod=mod,
                ),
                RenderField(label="Total GPU (cores)", path="$.max_gpu", mod=mod),
            ]
            ram_fields = [
                RenderField(label="Total Memory (MB)", path="$.max_memory", mod=mod),
                RenderField(
                    label="Memory per Service (MB)",
                    path="$.max_memory_per_service",
                    mod=mod,
                ),
                RenderField(
                    label="Memory per Task (MB)", path="$.max_memory_per_task", mod=mod
                ),
            ]
            ephemeral_storage_fields = [
                RenderField(
                    label="Ephemeral Storage (MB)",
                    path="$.max_ephemeral_storage",
                    mod=mod,
                ),
                RenderField(
                    label="Ephemeral Storage per Service (MB)",
                    path="$.max_ephemeral_storage_per_service",
                    mod=mod,
                ),
                RenderField(
                    label="Ephemeral Storage per Task (MB)",
                    path="$.max_ephemeral_storage_per_task",
                    mod=mod,
                ),
            ]
            persistent_storage_fields = [
                RenderField(
                    label="Total Persistent Storage (MB)",
                    path="$.max_persistent_storage",
                    mod=mod,
                ),
                RenderField(
                    label="Persistent Storage Size (MB)",
                    path="$.max_persistent_volume_size",
                    mod=mod,
                ),
                RenderField(
                    label="Number of Persistent Volumes",
                    path="$.max_persistent_volumes",
                    mod=mod,
                ),
            ]

            project_limits_fields = [
                RenderField(label="Total Projects", path="$.max_projects", mod=mod),
                RenderField(label="Total Stages", path="$.max_stages", mod=mod),
                RenderField(label="Total Builds", path="$.max_builds", mod=mod),
                RenderField(label="Total Private Images", path="$.max_images", mod=mod),
                RenderField(label="Total Sources", path="$.max_sources", mod=mod),
                RenderField(label="Total Pipelines", path="$.max_pipelines", mod=mod),
                RenderField(label="Total Tasks", path="$.max_tasks", mod=mod),
                RenderField(label="Total Notebooks", path="$.max_notebooks", mod=mod),
                RenderField(label="Total Services", path="$.max_services", mod=mod),
                RenderField(label="Total Secrets", path="$.max_secrets", mod=mod),
                RenderField(
                    label="Total Config-maps", path="$.max_configmaps", mod=mod
                ),
                # RenderField(label='Total Concurrent Runs', path='$.max_concurrent_workflows', mod=mod),
            ]
            compute_fields = (
                cpu_fields
                + ram_fields
                + ephemeral_storage_fields
                + persistent_storage_fields
            )

            click.echo()
            click.echo(f"Resource Quotas for Organization: {user_org.name}")
            click.echo(f"Quota Tier: {user_org.tier.name}")
            click.echo()
            click.echo("Compute Resources:             (Usage / Limit)")
            click.echo("---------------------------------------------")
            click.echo(
                Renderer(data=quota_data, fields=compute_fields).render_table(
                    tablefmt="plain"
                )
            )
            click.echo()
            click.echo("Project Resource Limits:   (Usage / Limit)")
            click.echo("------------------------------------------")
            click.echo(
                Renderer(data=quota_data, fields=project_limits_fields).render_table(
                    tablefmt="plain"
                )
            )
        return 0


@usage.command(name="org", help="Inspect aggregated PRAX Organization usage")
@click.pass_context
@click.argument("org", type=str)
@click.option(
    "--project-name",
    default=None,
    type=str,
    help="Limit usage aggregation to a project name",
)
@click.option(
    "--start",
    default=None,
    type=str,
    help="Start time for range query (ISO 8601)",
)
@click.option(
    "--end",
    default=None,
    type=str,
    help="End time for range query (ISO 8601)",
)
@click.option(
    "--step",
    default=None,
    type=str,
    help="Prometheus step, e.g. 5m or 1h",
)
@click.option(
    "--output",
    type=click.Choice(["summary", "yaml", "json"]),
    default="summary",
    show_default=True,
    help="Output format",
)
@login_required
def get_org_usage(
    ctx: click.Context,
    org: str,
    output: str,
    **filters,
):
    client = PRAXClient(ctx)
    usage_data = client.get_org_usage(
        org, **{k: v for k, v in filters.items() if v is not None}
    )
    if isinstance(usage_data, models.ErrorResponse):
        click.echo(f" {err} Error fetching organization usage:")
        echoerr(usage_data)
        return 1
    if output == "json":
        click.echo(Renderer(data=usage_data, fields=[]).render(output_format="json"))
    elif output == "yaml":
        click.echo(yaml.safe_dump(usage_data, sort_keys=False))
    else:
        click.echo(render_org_usage_summary(usage_data))
    return 0


@create.command(name="user-secret", help="Create a new PRAX User Secret (API Token)")
@click.pass_context
@click.argument("name", type=str)
@click.option(
    "--org",
    help="Organization name. Defaults to your current Org.",
    default=None,
    type=str,
)
@click.option("--description", help="Secret description", type=str, default=None)
@click.option(
    "--data", "-d", help="Secret data key=value pairs", type=str, multiple=True
)
@login_required
def create_user_secret(
    ctx: click.Context,
    name: str,
    org: str | None,
    description: str | None,
    data: list[str],
):
    client = PRAXClient(ctx)
    users = client.get_users()

    if isinstance(users, models.ErrorResponse):
        click.echo(f" {err} Error fetching User information:")
        echoerr(users)
        return 1
    elif users:
        user = users[0]
    else:
        click.echo(f" {err} No user information found.")
        return 1

    if not user.current_org:
        click.echo(
            f" {err} No organization specified and user '{user.username}' has no current Org."
        )
        return 1

    org = org or user.current_org.name
    user_id = getattr(user.email, "root", user.username)

    if org not in user.admin_orgs:
        click.echo(f" {err} Failed to create or update User-Secret!")
        click.echo(
            f" {wrn} User '{user_id}' cannot manage User Resources from Organization '{org}'"
        )
        return 1

    secret_data = {}
    for item in data:
        parts = item.split("=", 1)
        if len(parts) != 2 or not parts[0]:
            click.echo(f" {err} Failed to create or update User-Secret!")
            click.echo(
                f" {wrn} Error parsing secret data. Please provide key=value pairs."
            )
            return 1
        secret_data[parts[0]] = parts[1]

    secret = client.create_or_update_user_secret(name, org, secret_data, description)

    if isinstance(secret, models.ErrorResponse):
        click.echo(f" {err} Failed to create or update User-Secret!")
        echoerr(secret)
        return 1
    else:
        click.echo(
            f" {chk} User-Secret '{secret.name}' created successfully in '{org}' namespace!"
        )
