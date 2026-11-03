/** The items shown in the mobile bottom bar: those flagged `primary`, or the first five. */
export function bottomNavItems(nav) {
  const primary = nav.filter((item) => item.primary);
  return (primary.length ? primary : nav).slice(0, 5);
}
