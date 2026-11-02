const PATHS = {
  home: 'M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
  assignments: 'M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h5',
  groups:
    'M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm8 0a3 3 0 1 0 0-6M2 20c0-3 3-5 6-5s6 2 6 5M16 15c3 0 6 2 6 5',
  schedule: 'M4 6h16v15H4zM4 10h16M8 3v4M16 3v4',
  attendance: 'M4 6h16v15H4zM4 10h16M8 15l2.5 2.5L16 13',
  progress: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  achievements:
    'M8 4h8v5a4 4 0 0 1-8 0zM8 6H4a3 3 0 0 0 4 4M16 6h4a3 3 0 0 1-4 4M12 13v4M8 21h8M9 17h6',
  profile: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 4-6 8-6s8 2 8 6',
  puzzle: 'M7 21h10M8 17h8l-1-6 2-3-3-1-2-3-2 3-2 1 1 3z',
  users: 'M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 20c0-3 3-5 6-5s6 2 6 5M17 11h4M19 9v4',
  reports: 'M5 3h10l4 4v14H5zM9 17v-3M12 17v-6M15 17v-4',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
};

export default function NavIcon({ name }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={PATHS[name] ?? PATHS.more} />
    </svg>
  );
}
