import { useState } from 'react';
import { errorMessage, fieldErrors } from '../trainer/api';
import { toast } from '../trainer/components/toastStore';

/**
 * Submission state for a dialog form: `run(action, successMessage)` calls the
 * API, shows a toast on success and keeps field errors (from a 422) or a
 * general error message. Resolves to the API result, or undefined on failure.
 */
export function useSubmit() {
  const [state, setState] = useState({ busy: false, error: null, fields: {} });

  async function run(action, successMessage) {
    setState({ busy: true, error: null, fields: {} });
    try {
      const result = await action();
      setState({ busy: false, error: null, fields: {} });
      if (successMessage) toast.success(successMessage);
      return result ?? true;
    } catch (error) {
      const fields = fieldErrors(error);
      setState({
        busy: false,
        error: Object.keys(fields).length ? null : errorMessage(error),
        fields,
      });
      return undefined;
    }
  }

  const reset = () => setState({ busy: false, error: null, fields: {} });

  return { ...state, run, reset };
}
