from statistics import mean
from scipy.stats import ks_2samp

IGNORE_WORDS = ('time', 'date', 'created', 'timestamp')


def _ignored(path):
    last = path.rsplit('.', 1)[-1].lower()
    return any(word in last for word in IGNORE_WORDS)


def compare_values(old_numbers, new_numbers, old_nulls, new_nulls,
                   d_threshold=0.5, p_threshold=0.01,
                   null_threshold=0.3, min_samples=5,
                   min_rel_change=0.1):
    value_shift = {}
    for path in new_numbers:
        if path not in old_numbers or _ignored(path):
            continue
        old_vals = old_numbers[path]
        new_vals = new_numbers[path]
        if len(old_vals) < min_samples or len(new_vals) < min_samples:
            continue

        old_mean = mean(old_vals)
        new_mean = mean(new_vals)
        rel_change = abs(new_mean - old_mean) / max(abs(old_mean), 1e-9)

        d, p = ks_2samp(old_vals, new_vals)
        if d >= d_threshold and p < p_threshold and rel_change >= min_rel_change:
            value_shift[path] = {
                'ks_stat': round(float(d), 3),
                'p_value': round(float(p), 6),
                'old_mean': round(old_mean, 2),
                'new_mean': round(new_mean, 2),
                'mean_change': round(rel_change, 3),
            }

    null_shift = {}
    for path in new_nulls:
        if path not in old_nulls:
            continue
        old_null, old_total = old_nulls[path]
        new_null, new_total = new_nulls[path]
        if old_total < min_samples or new_total < min_samples:
            continue
        old_rate = old_null / old_total
        new_rate = new_null / new_total
        if abs(new_rate - old_rate) >= null_threshold:
            null_shift[path] = {'was': round(old_rate, 3), 'now': round(new_rate, 3)}

    return {'value_shift': value_shift, 'null_shift': null_shift}