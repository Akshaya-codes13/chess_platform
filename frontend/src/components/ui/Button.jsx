import { Link } from '../../routes/router';

/** Button, or a link styled as one when `to` is given. */
export default function Button({
  variant = 'primary',
  size = 'md',
  to,
  className = '',
  type = 'button',
  ...rest
}) {
  const classes = `btn btn-${variant} btn-${size} ${className}`.trim();
  if (to) return <Link to={to} className={classes} {...rest} />;
  return <button type={type} className={classes} {...rest} />;
}
