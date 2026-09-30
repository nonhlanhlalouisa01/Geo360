interface VerdictProps {
  tone: 'pass' | 'fail'
  label: string
  title: string
  reason: string
}

/**
 * A verdict is conveyed by an icon, a text label and the reason — never by
 * colour alone, so it stays readable for colour-blind users and screen readers.
 */
export function Verdict({ tone, label, title, reason }: VerdictProps) {
  const passed = tone === 'pass'
  return (
    <div className={`verdict verdict--${tone}`} role="status">
      <span className="verdict__icon" aria-hidden="true">
        {passed ? (
          <svg viewBox="0 0 24 24" width="48" height="48" focusable="false">
            <path
              d="M4 12.8 9.2 18 20 6.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="48" height="48" focusable="false">
            <path
              d="M5.5 5.5 18.5 18.5M18.5 5.5 5.5 18.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
            />
          </svg>
        )}
      </span>
      <div className="verdict__body">
        <p className="verdict__label">
          <span className="verdict__badge">{label}</span> {title}
        </p>
        <p className="verdict__reason">{reason}</p>
      </div>
    </div>
  )
}
