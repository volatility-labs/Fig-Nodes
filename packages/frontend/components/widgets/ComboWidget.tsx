import { useState, useEffect, useRef, useCallback } from 'react';
import { registerWidget, type WidgetProps } from './widget-registry';

function ComboWidget({ widget, value, onChange }: WidgetProps) {
  const strValue = value != null ? String(value) : '';
  const staticOptions = (widget.options?.options as Array<string | number | boolean>) ?? [];
  const dataSource = widget.dataSource;

  // Plain static dropdown — no dataSource
  if (!dataSource) {
    return (
      <div className="fig-widget">
        {widget.label && <label className="fig-widget-label">{widget.label}</label>}
        <select
          className="fig-widget-select"
          value={strValue}
          onChange={(e) => onChange(e.target.value)}
          onPointerDown={(e) => e.stopPropagation()}
        >
          {staticOptions.map((opt) => (
            <option key={String(opt)} value={String(opt)}>
              {String(opt)}
            </option>
          ))}
        </select>
      </div>
    );
  }

  // Searchable combo with dynamic dataSource
  return <SearchableCombo widget={widget} value={value} onChange={onChange} />;
}

// Separated component so hooks are always called unconditionally
function SearchableCombo({ widget, value, onChange }: WidgetProps) {
  const strValue = value != null ? String(value) : '';
  const dataSource = widget.dataSource!;
  const staticOptions = (widget.options?.options as Array<string | number | boolean>) ?? [];

  const [fetchedOptions, setFetchedOptions] = useState<string[]>([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    fetch(dataSource.endpoint, {
      method: dataSource.method ?? 'GET',
      headers: dataSource.headers,
    })
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        let items = dataSource.transform ? data[dataSource.transform] : data;
        if (Array.isArray(items) && dataSource.valueField) {
          items = items.map((i: Record<string, unknown>) => String(i[dataSource.valueField!]));
        } else if (Array.isArray(items)) {
          items = items.map(String);
        } else {
          items = [];
        }
        setFetchedOptions(items);
      })
      .catch(() => {
        if (cancelled) return;
        const fallback = dataSource.fallback ?? staticOptions;
        setFetchedOptions(fallback.map(String));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [dataSource.endpoint]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as HTMLElement)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const filtered = fetchedOptions.filter((o) =>
    o.toLowerCase().includes(filter.toLowerCase()),
  );

  const handleSelect = useCallback(
    (opt: string) => {
      onChange(opt);
      setFilter('');
      setOpen(false);
    },
    [onChange],
  );

  return (
    <div className="fig-widget fig-widget-searchable-combo" ref={containerRef}>
      {widget.label && <label className="fig-widget-label">{widget.label}</label>}
      <input
        className="fig-widget-input"
        type="text"
        value={open ? filter : strValue}
        placeholder={loading ? 'Loading...' : 'Search...'}
        onChange={(e) => {
          setFilter(e.target.value);
          if (!open) setOpen(true);
        }}
        onFocus={() => {
          setFilter('');
          setOpen(true);
        }}
        onPointerDown={(e) => e.stopPropagation()}
      />
      {open && (
        <div
          className="fig-combo-dropdown"
          onPointerDown={(e) => e.stopPropagation()}
          onWheel={(e) => e.stopPropagation()}
        >
          {filtered.length === 0 && (
            <div className="fig-combo-dropdown-empty">
              {loading ? 'Loading...' : 'No matches'}
            </div>
          )}
          {filtered.slice(0, 200).map((opt) => (
            <div
              key={opt}
              className={`fig-combo-dropdown-item${opt === strValue ? ' selected' : ''}`}
              onMouseDown={(e) => {
                e.preventDefault();
                handleSelect(opt);
              }}
            >
              {opt}
            </div>
          ))}
          {filtered.length > 200 && (
            <div className="fig-combo-dropdown-empty">
              {filtered.length - 200} more — refine search
            </div>
          )}
        </div>
      )}
    </div>
  );
}

registerWidget('combo', ComboWidget);
export default ComboWidget;
