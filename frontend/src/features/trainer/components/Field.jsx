import { useId } from 'react';

/** Label + control + hint/error, wired up with aria attributes. */
export function Field({ label, error, hint, required, children }) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className={`tr-field${error ? ' tr-field--error' : ''}`}>
      <label htmlFor={id} className="tr-field__label">
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {children({
        id,
        'aria-describedby': describedBy,
        'aria-invalid': error ? true : undefined,
        required,
      })}
      {error ? (
        <p id={`${id}-error`} className="tr-field__error">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="tr-field__hint">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

export function TextField({ label, error, hint, required, value, onChange, ...props }) {
  return (
    <Field label={label} error={error} hint={hint} required={required}>
      {(aria) => (
        <input
          className="tr-input"
          value={value ?? ''}
          onChange={(event) => onChange(event.target.value)}
          {...aria}
          {...props}
        />
      )}
    </Field>
  );
}

export function TextArea({ label, error, hint, required, value, onChange, rows = 3, ...props }) {
  return (
    <Field label={label} error={error} hint={hint} required={required}>
      {(aria) => (
        <textarea
          className="tr-input"
          rows={rows}
          value={value ?? ''}
          onChange={(event) => onChange(event.target.value)}
          {...aria}
          {...props}
        />
      )}
    </Field>
  );
}

export function SelectField({
  label,
  error,
  hint,
  required,
  value,
  onChange,
  options,
  placeholder,
  ...props
}) {
  return (
    <Field label={label} error={error} hint={hint} required={required}>
      {(aria) => (
        <select
          className="tr-input"
          value={value ?? ''}
          onChange={(event) => onChange(event.target.value)}
          {...aria}
          {...props}
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}

/** Compact unlabeled-looking filter control that still has an accessible label. */
export function FilterSelect({ label, value, onChange, options, allLabel = 'All' }) {
  const id = useId();
  return (
    <div className="tr-filter">
      <label htmlFor={id} className="tr-filter__label">
        {label}
      </label>
      <select
        id={id}
        className="tr-input tr-input--sm"
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value || null)}
      >
        <option value="">{allLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder = 'Search…', label = 'Search' }) {
  const id = useId();
  return (
    <div className="tr-filter tr-filter--grow">
      <label htmlFor={id} className="tr-filter__label">
        {label}
      </label>
      <input
        id={id}
        type="search"
        className="tr-input tr-input--sm"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
