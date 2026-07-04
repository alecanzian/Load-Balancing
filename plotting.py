# plotting.py

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.ticker
import matplotlib.pyplot as plt

COLORS = ['#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4', '#42d4f4', '#f032e6']
_SCALE = {'s': 1, 'ms': 1e3, 'us': 1e6, 'ns': 1e9}


# ----------------------------------------------------
# helpers
# ----------------------------------------------------

def _filter(all_results, alpha, load, strategies):
    data = all_results[load][alpha]
    if strategies is None:
        return data
    unknown = [s for s in strategies if s not in data]
    if unknown:
        raise ValueError(f"Strategies {unknown} not in results. Available: {list(data.keys())}")
    return {k: data[k] for k in strategies}


def _suffix(strategies):
    return '' if strategies is None else '_' + '_'.join(strategies)


def _sim_info(n_jobs, base_work):
    return f"n={n_jobs}, base_work={base_work}"


def _save(fig, out_dir, fname):
    fig.savefig(os.path.join(out_dir, fname), format="png", dpi=300, bbox_inches='tight')
    plt.close(fig)


def _log_axis(axis):
    axis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda x, _: f'{x:,.0f}' if x >= 1 else f'{x:.3f}'))
    axis.set_minor_locator(matplotlib.ticker.LogLocator(subs='all'))
    axis.set_minor_formatter(matplotlib.ticker.FuncFormatter(
        lambda x, _: f'{x:,.0f}' if x >= 1 else ''))


# ----------------------------------------------------
# per-(alpha, lambda) plots
# ----------------------------------------------------

def plot_response_time_cdf(all_results, alpha, load, out_dir, time_unit,
                           n_jobs, base_work, strategies=None):
    scale = _SCALE[time_unit]
    fig, ax = plt.subplots(figsize=(16, 9))
    for (name, data), color in zip(_filter(all_results, alpha, load, strategies).items(), COLORS):
        sorted_times = np.sort(data["response_times"]) * scale
        cdf = np.arange(1, len(sorted_times) + 1) / len(sorted_times)
        ax.plot(sorted_times, cdf, label=name, color=color, linewidth=2)
    ax.set_xscale('log')
    _log_axis(ax.xaxis)
    ax.tick_params(axis='x', which='both', rotation=45, labelsize=7)
    ax.grid(True, which='both', axis='both', alpha=0.3)   # add this
    ax.set_xlabel(f"Response time ({time_unit}) — log scale")
    ax.set_ylabel("Fraction of jobs completed (CDF)")
    ax.set_title(f"Response time CDF — α={alpha}, λ={load} — {_sim_info(n_jobs, base_work)}")
    ax.legend()
    fig.tight_layout()
    fname = (f"response_time_cdf_alpha{str(alpha).replace('.', '_')}"
             f"_load{str(load).replace('.', '_')}{_suffix(strategies)}.png")
    _save(fig, out_dir, fname)


def plot_server_loads(all_results, alpha, load, out_dir, n_jobs, base_work, strategies=None):
    filtered    = _filter(all_results, alpha, load, strategies)
    strat_names = list(filtered.keys())

    fig, ax = plt.subplots(figsize=(16, 9))
    x     = np.arange(3)
    width = 0.8 / len(strat_names)

    for i, (name, color) in enumerate(zip(strat_names, COLORS)):
        ax.bar(x + i * width, filtered[name]["server_loads"], width, label=name, color=color)

    ax.set_xticks(x + width * (len(strat_names) - 1) / 2)
    ax.set_xticklabels(["Server 1", "Server 2", "Server 3"])
    ax.set_ylabel("Load")
    ax.set_title(f"Server load distribution — α={alpha}, λ={load} — {_sim_info(n_jobs, base_work)}")
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.1))
    ax.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(0.02))
    ax.tick_params(axis='y', which='minor', labelsize=7)
    ax.grid(True, which='both', axis='y', alpha=0.3) 
    ax.legend()
    fig.tight_layout()
    fname = (f"server_loads_alpha{str(alpha).replace('.', '_')}"
             f"_load{str(load).replace('.', '_')}{_suffix(strategies)}.png")
    _save(fig, out_dir, fname)


def plot_response_time_boxplot(all_results, alpha, load, out_dir, n_jobs, base_work,
                               time_unit='ms', strategies=None):
    scale       = _SCALE[time_unit]
    filtered    = _filter(all_results, alpha, load, strategies)
    strat_names = list(filtered.keys())
    data        = [np.array(filtered[s]['response_times']) * scale for s in strat_names]

    fig, ax = plt.subplots(figsize=(16, 9))
    bp = ax.boxplot(data, patch_artist=True, notch=False,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], COLORS):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_yscale('log')
    _log_axis(ax.yaxis)
    ax.tick_params(axis='y', which='minor', labelsize=7)
    ax.set_xticks(range(1, len(strat_names) + 1))
    ax.set_xticklabels(strat_names, rotation=15)
    ax.set_ylabel(f"Response time ({time_unit}) — log scale")
    ax.set_title(f"Response time distribution — α={alpha}, λ={load} — {_sim_info(n_jobs, base_work)}")
    ax.legend(bp['boxes'], strat_names, loc='upper right')
    fig.tight_layout()
    fname = (f"boxplot_alpha{str(alpha).replace('.', '_')}"
             f"_load{str(load).replace('.', '_')}{_suffix(strategies)}.png")
    _save(fig, out_dir, fname)


# ----------------------------------------------------
# sweep plots (simulation 1)
# ----------------------------------------------------

def plot_sweep_metric(all_results, points, x_values, xlabel, metric, out_dir,
                      title, fname, strategies, time_unit='ms'):
    """Line plot of a scalar metric over a sweep, one line per strategy.

    points   — list of (alpha, load) tuples, aligned with x_values
    metric   — 'mean_response_time' | 'avg_load' | 'load_variance'
    """
    scale = _SCALE[time_unit]
    fig, ax = plt.subplots(figsize=(12, 7))
    for name, color in zip(strategies, COLORS):
        ys = []
        for alpha, load in points:
            d = all_results[load][alpha][name]
            if metric == 'mean_response_time':
                ys.append(np.mean(d['response_times']) * scale)
            elif metric == 'avg_load':
                ys.append(np.mean(d['server_loads']))
            elif metric == 'load_variance':
                ys.append(np.var(d['server_loads']))
            else:
                raise ValueError(f"Unknown metric '{metric}'")
        ax.plot(x_values, ys, marker='o', linewidth=2, label=name, color=color)

    ylabels = {'mean_response_time': f"Mean response time ({time_unit})",
               'avg_load': "Average server load",
               'load_variance': "Load variance across servers"}
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabels[metric])
    ax.set_title(title)
    ax.grid(True)
    ax.legend()
    fig.tight_layout()
    _save(fig, out_dir, fname)


def plot_sweep_cdf(all_results, points, labels, strategy, out_dir,
                   title, fname, time_unit='ms'):
    """Response time CDFs of one strategy across the values of a sweep."""
    scale = _SCALE[time_unit]
    fig, ax = plt.subplots(figsize=(16, 9))
    for (alpha, load), label, color in zip(points, labels, COLORS + COLORS):
        data = all_results[load][alpha][strategy]
        sorted_times = np.sort(data["response_times"]) * scale
        cdf = np.arange(1, len(sorted_times) + 1) / len(sorted_times)
        ax.plot(sorted_times, cdf, label=label, linewidth=2)

    ax.set_xscale('log')
    _log_axis(ax.xaxis)
    ax.tick_params(axis='x', which='both', rotation=45, labelsize=7)
    ax.set_xlabel(f"Response time ({time_unit}) — log scale")
    ax.set_ylabel("Fraction of jobs completed (CDF)")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    _save(fig, out_dir, fname)


# ----------------------------------------------------
# grid plots (simulation 2)
# ----------------------------------------------------

def plot_avg_load(all_results, out_dir, strategies=None):
    """Average server load vs alpha, one panel per load rate."""
    loads = list(all_results.keys())
    fig, axes = plt.subplots(1, len(loads), figsize=(16, 6), sharey=True)
    if len(loads) == 1:
        axes = [axes]

    for ax, load in zip(axes, loads):
        alphas = list(all_results[load].keys())
        names = _filter(all_results, alphas[0], load, strategies).keys()
        for name, color in zip(names, COLORS):
            avg_loads = [np.mean(all_results[load][a][name]['server_loads']) for a in alphas]
            ax.plot(alphas, avg_loads, label=name, color=color, linewidth=2, marker='o')
        ax.set_title(f"λ={load}")
        ax.set_xlabel("α (Pareto shape)")
        ax.set_ylabel("Average load" if ax is axes[0] else "")
        ax.legend(fontsize=7)
        ax.grid(True)

    fig.suptitle("Average server load — by α and λ", fontsize=14, fontweight='bold')
    fig.tight_layout()
    _save(fig, out_dir, f"avg_load{_suffix(strategies)}.png")


def plot_load_variance(all_results, out_dir, strategies=None):
    """Load variance across servers vs alpha, one panel per load rate."""
    loads = list(all_results.keys())
    fig, axes = plt.subplots(1, len(loads), figsize=(16, 6), sharey=True)
    if len(loads) == 1:
        axes = [axes]

    for ax, load in zip(axes, loads):
        alphas = list(all_results[load].keys())
        names = _filter(all_results, alphas[0], load, strategies).keys()
        for name, color in zip(names, COLORS):
            variances = [np.var(all_results[load][a][name]['server_loads']) for a in alphas]
            ax.plot(alphas, variances, label=name, color=color, linewidth=2, marker='o')
        ax.set_title(f"λ={load}")
        ax.set_xlabel("α (Pareto shape)")
        ax.set_ylabel("Load variance across servers" if ax is axes[0] else "")
        ax.legend(fontsize=7)
        ax.grid(True)

    fig.suptitle("Load variance across servers — by α and λ", fontsize=14, fontweight='bold')
    fig.tight_layout()
    _save(fig, out_dir, f"load_variance{_suffix(strategies)}.png")


def plot_summary_table(all_results, out_dir, n_jobs, base_work, time_unit='ms', strategies=None):
    scale = _SCALE[time_unit]
    rows  = []
    for load in all_results:
        for alpha in all_results[load]:
            for name, data in _filter(all_results, alpha, load, strategies).items():
                rt = np.array(data['response_times']) * scale
                rows.append([
                    name, alpha, load,
                    f"{np.mean(rt):.2f}",
                    f"{np.median(rt):.2f}",
                    f"{np.percentile(rt, 90):.2f}",
                    f"{np.percentile(rt, 99):.2f}",
                ])

    cols = ['Strategy', 'α', 'λ', f'Mean ({time_unit})', f'Median ({time_unit})',
            f'P90 ({time_unit})', f'P99 ({time_unit})']

    fig, ax = plt.subplots(figsize=(16, max(4, len(rows) * 0.4 + 1)))
    ax.axis('off')
    table = ax.table(cellText=rows, colLabels=cols, cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.auto_set_column_width(col=list(range(len(cols))))

    for j in range(len(cols)):
        table[0, j].set_facecolor('#2c3e50')
        table[0, j].set_text_props(color='white', fontweight='bold')
    for i in range(1, len(rows) + 1):
        color = '#f2f2f2' if i % 2 == 0 else 'white'
        for j in range(len(cols)):
            table[i, j].set_facecolor(color)

    ax.set_title(f"Response Time Summary — {_sim_info(n_jobs, base_work)}",
                 fontsize=14, fontweight='bold', pad=20)
    _save(fig, out_dir, f"summary_table{_suffix(strategies)}.png")