import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";

export type SearchableSelectOption = {
  value: string;
  label: string;
  keywords?: string;
  meta?: ReactNode;
};

export function SearchableSelect({
  label,
  placeholder,
  value,
  searchText,
  options,
  emptyText = "No matches found.",
  loading = false,
  disabled = false,
  onSearchTextChange,
  onChange,
  className = "",
}: {
  label?: string;
  placeholder?: string;
  value: SearchableSelectOption | null;
  searchText: string;
  options: SearchableSelectOption[];
  emptyText?: string;
  loading?: boolean;
  disabled?: boolean;
  onSearchTextChange: (value: string) => void;
  onChange: (option: SearchableSelectOption | null) => void;
  className?: string;
}) {
  const fieldId = useId();
  const listboxId = `${fieldId}-listbox`;
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const visibleValue = open ? searchText || value?.label || "" : value?.label || searchText;
  const normalizedQuery = searchText.trim().toLowerCase();
  const filteredOptions = useMemo(() => {
    if (!normalizedQuery) return options;
    return options.filter((option) => {
      const haystack = `${option.label} ${option.keywords || ""}`.toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [options, normalizedQuery]);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setActiveIndex(0);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  useEffect(() => {
    setActiveIndex((current) => {
      if (filteredOptions.length === 0) return 0;
      return Math.min(current, filteredOptions.length - 1);
    });
  }, [filteredOptions.length]);

  function commit(option: SearchableSelectOption | null) {
    onChange(option);
    onSearchTextChange("");
    setOpen(false);
    setActiveIndex(0);
  }

  return (
    <div ref={rootRef} className={`field searchable-select ${className}`.trim()}>
      {label ? <span className="searchable-select__label">{label}</span> : null}
      <div className={`searchable-select__control${open ? " is-open" : ""}${disabled ? " is-disabled" : ""}`}>
        <input
          ref={inputRef}
          id={fieldId}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-activedescendant={open && filteredOptions[activeIndex] ? `${fieldId}-option-${filteredOptions[activeIndex]!.value}` : undefined}
          value={visibleValue}
          placeholder={placeholder}
          disabled={disabled}
          onFocus={() => {
            setOpen(true);
            requestAnimationFrame(() => inputRef.current?.select());
          }}
          onClick={() => {
            setOpen(true);
            requestAnimationFrame(() => inputRef.current?.select());
          }}
          onChange={(event) => {
            if (value) onChange(null);
            onSearchTextChange(event.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setOpen(true);
              setActiveIndex((current) => Math.min(current + 1, Math.max(filteredOptions.length - 1, 0)));
              return;
            }
            if (event.key === "ArrowUp") {
              event.preventDefault();
              setOpen(true);
              setActiveIndex((current) => Math.max(current - 1, 0));
              return;
            }
            if (event.key === "Enter" && open && filteredOptions[activeIndex]) {
              event.preventDefault();
              commit(filteredOptions[activeIndex] || null);
              return;
            }
            if (event.key === "Escape") {
              event.preventDefault();
              onSearchTextChange("");
              setOpen(false);
              inputRef.current?.blur();
            }
          }}
        />
        {value ? (
          <button
            type="button"
            className="searchable-select__clear"
            onClick={() => {
              commit(null);
              inputRef.current?.focus();
            }}
            aria-label="Clear selection"
          >
            Clear
          </button>
        ) : null}
      </div>
      {open ? (
        <div className="searchable-select__menu" role="listbox" id={listboxId}>
          {loading ? <div className="searchable-select__empty">Loading…</div> : null}
          {!loading && filteredOptions.length === 0 ? <div className="searchable-select__empty">{emptyText}</div> : null}
          {!loading && filteredOptions.length > 0 ? (
            <div className="searchable-select__options">
              {filteredOptions.map((option, index) => (
                <button
                  key={option.value}
                  id={`${fieldId}-option-${option.value}`}
                  type="button"
                  role="option"
                  aria-selected={value?.value === option.value}
                  className={`searchable-select__option${index === activeIndex ? " is-active" : ""}${value?.value === option.value ? " is-selected" : ""}`}
                  onMouseEnter={() => setActiveIndex(index)}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => commit(option)}
                >
                  <span className="searchable-select__option-label">{option.label}</span>
                  {option.meta ? <span className="searchable-select__option-meta">{option.meta}</span> : null}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
