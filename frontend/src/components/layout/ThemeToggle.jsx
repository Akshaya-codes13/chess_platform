import { useTheme } from '../../store/themeStore';

const OPTIONS = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="theme-toggle" role="group" aria-label="Color theme">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={theme === option.value}
          onClick={() => setTheme(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
