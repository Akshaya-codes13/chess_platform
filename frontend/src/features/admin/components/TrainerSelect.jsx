import { SelectField } from '../../trainer/components/Field';
import { useLoader } from '../../trainer/hooks';
import { adminApi } from '../api';

const TRAINER_LIMIT = 100;

/** Select an active trainer by user ID. */
export default function TrainerSelect({ label = 'Trainer', value, onChange, error, required }) {
  const result = useLoader(
    () => adminApi.trainers({ is_active: true, page_size: TRAINER_LIMIT }),
    [],
  );
  const trainers = result.data?.items ?? [];
  const more = (result.data?.total ?? 0) > trainers.length;

  return (
    <SelectField
      label={label}
      value={value}
      onChange={onChange}
      required={required}
      placeholder={result.data ? 'Choose a trainer' : 'Loading trainers…'}
      options={trainers.map((trainer) => ({
        value: trainer.id,
        label: trainer.specialization
          ? `${trainer.full_name} — ${trainer.specialization}`
          : trainer.full_name,
      }))}
      error={
        error ||
        (result.error ? 'Could not load trainers.' : null) ||
        (result.data && !trainers.length ? 'Create an active trainer first.' : null)
      }
      hint={more ? `Showing the first ${TRAINER_LIMIT} active trainers by name.` : undefined}
    />
  );
}
