import { useEffect, useRef, useState } from 'react';
import { BASE_URL, api } from '../api';
import { CheckIcon } from '../icons';

interface PairingDialogProps {
  onPaired: () => void;
  onClose: () => void;
}

type PairState =
  | { phase: 'loading' }
  | { phase: 'error'; message: string }
  | { phase: 'waiting'; token: string; url: string }
  | { phase: 'claimed'; cameraName: string };

/** "Add phone or tablet" — shows a QR code for the hub's pairing URL and
 * waits for the device to claim it. Everything stays on the LAN. */
export function PairingDialog({ onPaired, onClose }: PairingDialogProps) {
  const [state, setState] = useState<PairState>({ phase: 'loading' });
  const pollRef = useRef<number>();

  useEffect(() => {
    let cancelled = false;

    api
      .startPairing()
      .then(({ token, url }) => {
        if (cancelled) return;
        setState({ phase: 'waiting', token, url });
      })
      .catch((err) =>
        setState({
          phase: 'error',
          message: `Could not start pairing: ${String(err)}`,
        }),
      );

    return () => {
      cancelled = true;
      window.clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (state.phase !== 'waiting') return;
    const { token } = state;
    pollRef.current = window.setInterval(async () => {
      try {
        const status = await api.pairingStatus(token);
        if (status.status === 'claimed') {
          window.clearInterval(pollRef.current);
          const settings = await api.getSettings();
          const cam = settings.cameras.find((c) => c.id === status.camera_id);
          setState({ phase: 'claimed', cameraName: cam?.name ?? 'Phone camera' });
          onPaired();
        } else if (status.status === 'expired') {
          window.clearInterval(pollRef.current);
          setState({
            phase: 'error',
            message: 'The pairing code expired. Close this and try again.',
          });
        }
      } catch {
        /* backend briefly unreachable: keep polling */
      }
    }, 1500);
    return () => window.clearInterval(pollRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase]);

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div
        className="dialog pairing"
        role="dialog"
        aria-modal="true"
        aria-label="Add phone or tablet camera"
        onClick={(e) => e.stopPropagation()}
      >
        <h3>Add a phone or tablet as a camera</h3>

        {state.phase === 'loading' && <p>Preparing a pairing code…</p>}

        {state.phase === 'error' && <p className="pairing-error">{state.message}</p>}

        {state.phase === 'waiting' && (
          <>
            <div className="qr-wrap">
              <img
                src={`${BASE_URL}/api/pairing/${state.token}/qr.png`}
                alt="Pairing QR code"
                width={196}
                height={196}
              />
            </div>
            <ol className="pairing-steps">
              <li>On the phone/tablet, open the camera app and scan this code.</li>
              <li>
                Accept the one-time certificate warning — the link is your own
                hub on this network, nothing leaves your home.
              </li>
              <li>Name the camera and tap “Start camera”.</li>
            </ol>
            <p className="pairing-url">
              or type this address: <code>{state.url}</code>
            </p>
            <div className="status">
              <span className="spinner small" aria-hidden /> Waiting for the
              device…
            </div>
          </>
        )}

        {state.phase === 'claimed' && (
          <div className="pairing-done">
            <span className="pairing-check">
              <CheckIcon size={22} />
            </span>
            <p>
              <strong>{state.cameraName}</strong> is paired and streaming. It
            appears under Live now — keep the device plugged in with its
              screen on.
            </p>
          </div>
        )}

        <div className="dialog-actions">
          <button className="btn" onClick={onClose}>
            {state.phase === 'claimed' ? 'Done' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  );
}
