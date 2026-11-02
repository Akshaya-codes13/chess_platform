import { useState } from 'react';
import { SelectField, TextArea, TextField } from '../../trainer/components/Field';
import { titleCase } from '../../trainer/format';
import { adminApi } from '../api';
import { useSubmit } from '../hooks';
import { compact, LEVEL_OPTIONS, ROLE_OPTIONS } from '../utils';
import {
  onlyErrors,
  validateEmail,
  validateName,
  validatePassword,
  validatePastDate,
  validateRange,
} from '../validation';
import FormDialog from './FormDialog';
import TrainerSelect from './TrainerSelect';

const EMPTY_ACCOUNT = {
  full_name: '',
  email: '',
  password: '',
  phone: '',
  specialization: '',
  experience_years: '',
  bio: '',
  trainer_user_id: '',
  level: 'beginner',
  chess_rating: '',
  date_of_birth: '',
};

function toInt(value) {
  return value === '' || value === null || value === undefined ? undefined : Number(value);
}

function TrainerProfileFields({ values, set, errors }) {
  return (
    <>
      <div className="tr-form-grid">
        <TextField
          label="Specialization"
          value={values.specialization}
          onChange={set('specialization')}
          maxLength={150}
        />
        <TextField
          label="Experience (years)"
          type="number"
          min={0}
          max={80}
          value={values.experience_years}
          onChange={set('experience_years')}
          error={errors.experience_years}
        />
      </div>
      <TextArea label="Bio" value={values.bio} onChange={set('bio')} maxLength={5000} />
    </>
  );
}

function StudentProfileFields({ values, set, errors, trainerRequired = true }) {
  return (
    <>
      <TrainerSelect
        label="Primary trainer"
        required={trainerRequired}
        value={values.trainer_user_id}
        onChange={set('trainer_user_id')}
        error={errors.trainer_user_id}
      />
      <div className="tr-form-grid">
        <SelectField
          label="Level"
          value={values.level}
          onChange={set('level')}
          options={LEVEL_OPTIONS}
        />
        <TextField
          label="Chess rating"
          type="number"
          min={0}
          max={4000}
          value={values.chess_rating}
          onChange={set('chess_rating')}
          error={errors.chess_rating}
        />
        <TextField
          label="Date of birth"
          type="date"
          value={values.date_of_birth}
          onChange={set('date_of_birth')}
          error={errors.date_of_birth}
        />
      </div>
    </>
  );
}

function profileErrors(role, values, { trainerRequired = true } = {}) {
  if (role === 'trainer') {
    return {
      experience_years: validateRange(values.experience_years, 0, 80, 'Experience'),
    };
  }
  if (role === 'student') {
    return {
      trainer_user_id:
        trainerRequired && !values.trainer_user_id ? 'Choose a primary trainer.' : null,
      chess_rating: validateRange(values.chess_rating, 0, 4000, 'Rating'),
      date_of_birth: validatePastDate(values.date_of_birth),
    };
  }
  return {};
}

function trainerProfileBody(values) {
  return compact({
    specialization: values.specialization.trim(),
    experience_years: toInt(values.experience_years),
    bio: values.bio.trim(),
  });
}

function studentProfileBody(values) {
  return compact({
    trainer_user_id: values.trainer_user_id,
    level: values.level,
    chess_rating: toInt(values.chess_rating),
    date_of_birth: values.date_of_birth,
  });
}

/** Create a trainer or student account. `role` fixes the role when given. */
export function AccountDialog({ open, role: fixedRole, onClose, onCreated }) {
  const [values, setValues] = useState({ ...EMPTY_ACCOUNT, role: fixedRole ?? 'student' });
  const [clientErrors, setClientErrors] = useState({});
  const submit = useSubmit();
  const role = fixedRole ?? values.role;
  const errors = { ...submit.fields, ...clientErrors };
  const set = (name) => (value) => setValues((current) => ({ ...current, [name]: value }));

  function close() {
    setValues({ ...EMPTY_ACCOUNT, role: fixedRole ?? 'student' });
    setClientErrors({});
    submit.reset();
    onClose();
  }

  async function handleSubmit() {
    const found = onlyErrors({
      full_name: validateName(values.full_name, 'Full name'),
      email: validateEmail(values.email),
      password: validatePassword(values.password),
      ...profileErrors(role, values),
    });
    setClientErrors(found);
    if (Object.keys(found).length) return;

    const body = {
      role,
      full_name: values.full_name.trim(),
      email: values.email.trim(),
      password: values.password,
      ...compact({ phone: values.phone.trim() }),
      ...(role === 'trainer'
        ? { trainer_profile: trainerProfileBody(values) }
        : { student_profile: studentProfileBody(values) }),
    };

    const user = await submit.run(() => adminApi.createUser(body), `${titleCase(role)} created.`);
    if (user) {
      close();
      onCreated?.(user);
    }
  }

  return (
    <FormDialog
      open={open}
      title={fixedRole ? `New ${fixedRole}` : 'New account'}
      submitLabel={`Create ${role}`}
      busy={submit.busy}
      error={submit.error || errors.student_profile || errors.trainer_profile}
      onSubmit={handleSubmit}
      onClose={close}
    >
      {!fixedRole && (
        <SelectField
          label="Role"
          value={values.role}
          onChange={set('role')}
          options={ROLE_OPTIONS.filter((option) => option.value !== 'admin')}
          hint="Admin access is granted by changing an existing user's role."
        />
      )}
      <div className="tr-form-grid">
        <TextField
          label="Full name"
          required
          value={values.full_name}
          onChange={set('full_name')}
          error={errors.full_name}
          maxLength={150}
          autoComplete="off"
        />
        <TextField
          label="Email"
          type="email"
          required
          value={values.email}
          onChange={set('email')}
          error={errors.email}
          autoComplete="off"
        />
        <TextField
          label="Initial password"
          type="password"
          required
          value={values.password}
          onChange={set('password')}
          error={errors.password}
          hint="At least 8 characters with a letter and a digit. Share it securely."
          autoComplete="new-password"
        />
        <TextField
          label="Phone"
          type="tel"
          value={values.phone}
          onChange={set('phone')}
          error={errors.phone}
          maxLength={20}
        />
      </div>
      {role === 'trainer' ? (
        <TrainerProfileFields values={values} set={set} errors={errors} />
      ) : (
        <StudentProfileFields values={values} set={set} errors={errors} />
      )}
    </FormDialog>
  );
}

function initialEditValues(user) {
  const trainer = user.trainer_profile ?? {};
  const student = user.student_profile ?? {};
  return {
    full_name: user.full_name,
    email: user.email,
    phone: user.phone ?? '',
    language: user.language,
    specialization: trainer.specialization ?? '',
    experience_years: trainer.experience_years ?? '',
    bio: trainer.bio ?? '',
    trainer_user_id: student.trainer?.id ?? '',
    level: student.level ?? 'beginner',
    chess_rating: student.chess_rating ?? '',
    date_of_birth: student.date_of_birth ?? '',
    notes: student.notes ?? '',
  };
}

/** Return only the keys whose value differs from `before`. */
function changed(after, before) {
  return Object.fromEntries(Object.entries(after).filter(([key, value]) => value !== before[key]));
}

/** Edit profile details. Role and status have their own controls. */
export function EditUserDialog({ open, user, onClose, onSaved }) {
  const [values, setValues] = useState(() => initialEditValues(user));
  const [clientErrors, setClientErrors] = useState({});
  const submit = useSubmit();
  const errors = { ...submit.fields, ...clientErrors };
  const set = (name) => (value) => setValues((current) => ({ ...current, [name]: value }));
  const hasStudentProfile = Boolean(user.student_profile);

  function close() {
    setValues(initialEditValues(user));
    setClientErrors({});
    submit.reset();
    onClose();
  }

  async function handleSubmit() {
    const found = onlyErrors({
      full_name: validateName(values.full_name, 'Full name'),
      email: validateEmail(values.email),
      ...profileErrors(user.role, values, { trainerRequired: false }),
    });
    setClientErrors(found);
    if (Object.keys(found).length) return;

    const before = initialEditValues(user);
    const body = changed(
      {
        full_name: values.full_name.trim(),
        email: values.email.trim(),
        phone: values.phone.trim() || null,
        language: values.language.trim(),
      },
      { ...before, phone: before.phone || null },
    );

    if (user.role === 'trainer') {
      const profile = changed(
        {
          specialization: values.specialization.trim() || null,
          experience_years: toInt(values.experience_years) ?? 0,
          bio: values.bio.trim() || null,
        },
        {
          specialization: before.specialization || null,
          experience_years: toInt(before.experience_years) ?? 0,
          bio: before.bio || null,
        },
      );
      if (Object.keys(profile).length) body.trainer_profile = profile;
    }

    if (user.role === 'student') {
      const profile = changed(
        {
          trainer_user_id: values.trainer_user_id || undefined,
          level: values.level,
          chess_rating: toInt(values.chess_rating),
          date_of_birth: values.date_of_birth || null,
          notes: values.notes.trim() || null,
        },
        {
          trainer_user_id: before.trainer_user_id || undefined,
          level: before.level,
          chess_rating: toInt(before.chess_rating),
          date_of_birth: before.date_of_birth || null,
          notes: before.notes || null,
        },
      );
      if (profile.trainer_user_id === undefined) delete profile.trainer_user_id;
      if (Object.keys(profile).length) body.student_profile = profile;
    }

    if (!Object.keys(body).length) {
      close();
      return;
    }

    const saved = await submit.run(() => adminApi.updateUser(user.id, body), 'Profile updated.');
    if (saved) {
      setClientErrors({});
      onSaved(saved);
      onClose();
    }
  }

  return (
    <FormDialog
      open={open}
      title={`Edit ${user.full_name}`}
      busy={submit.busy}
      error={submit.error || errors.student_profile || errors.trainer_profile}
      onSubmit={handleSubmit}
      onClose={close}
    >
      <div className="tr-form-grid">
        <TextField
          label="Full name"
          required
          value={values.full_name}
          onChange={set('full_name')}
          error={errors.full_name}
          maxLength={150}
        />
        <TextField
          label="Email"
          type="email"
          required
          value={values.email}
          onChange={set('email')}
          error={errors.email}
          hint="Changing it marks the address as unverified."
        />
        <TextField
          label="Phone"
          type="tel"
          value={values.phone}
          onChange={set('phone')}
          maxLength={20}
        />
        <TextField
          label="Language"
          value={values.language}
          onChange={set('language')}
          error={errors.language}
          maxLength={10}
        />
      </div>
      {user.role === 'trainer' && (
        <TrainerProfileFields values={values} set={set} errors={errors} />
      )}
      {user.role === 'student' && (
        <>
          {!hasStudentProfile && (
            <p className="tr-callout tr-callout--info">
              This student registered without a profile. Choose a primary trainer to create one.
            </p>
          )}
          <StudentProfileFields
            values={values}
            set={set}
            errors={errors}
            trainerRequired={!hasStudentProfile}
          />
          <TextArea label="Notes" value={values.notes} onChange={set('notes')} maxLength={5000} />
        </>
      )}
    </FormDialog>
  );
}

/** Change a user's role; the API enforces the safety rules. */
export function RoleDialog({ open, user, onClose, onSaved }) {
  const options = ROLE_OPTIONS.filter((option) => option.value !== user.role);
  const [role, setRole] = useState(options[0].value);
  const [trainerId, setTrainerId] = useState('');
  const submit = useSubmit();
  const needsTrainer = role === 'student' && !user.student_profile;

  function close() {
    setRole(options[0].value);
    setTrainerId('');
    submit.reset();
    onClose();
  }

  async function handleSubmit() {
    const body = { role, ...(needsTrainer || trainerId ? { trainer_user_id: trainerId } : {}) };
    if (needsTrainer && !trainerId) return;
    const saved = await submit.run(
      () => adminApi.changeRole(user.id, body),
      `${user.full_name} is now ${role === 'admin' ? 'an' : 'a'} ${role}.`,
    );
    if (saved) {
      onSaved(saved);
      close();
    }
  }

  return (
    <FormDialog
      open={open}
      title="Change role"
      submitLabel="Change role"
      busy={submit.busy}
      error={submit.error}
      onSubmit={handleSubmit}
      onClose={close}
    >
      <p>
        {user.full_name} is currently {user.role === 'admin' ? 'an' : 'a'}{' '}
        <strong>{user.role}</strong>.
      </p>
      <SelectField label="New role" value={role} onChange={setRole} options={options} />
      {role === 'admin' && (
        <p className="tr-callout tr-callout--error">
          Admins can manage every account, group and puzzle on the platform. Grant this only to
          trusted staff.
        </p>
      )}
      {needsTrainer && (
        <TrainerSelect
          label="Primary trainer"
          required
          value={trainerId}
          onChange={setTrainerId}
          error={submit.fields.trainer_user_id}
        />
      )}
      <p className="tr-muted">
        Existing profiles and history are kept. Trainers must hand over their groups and students,
        and students must leave their groups, before their role can change.
      </p>
    </FormDialog>
  );
}
