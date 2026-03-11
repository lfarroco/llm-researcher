import {
	useCallback,
	useMemo,
	useState,
	type ReactNode,
} from 'react';
import { ToastContext, type ToastType } from '../context/toastContext';

interface ToastItem {
	id: number;
	message: string;
	type: ToastType;
}

const styleByType: Record<ToastType, string> = {
	success: 'bg-green-600',
	error: 'bg-red-600',
	info: 'bg-gray-800',
};

export function ToastProvider({ children }: { children: ReactNode }) {
	const [toasts, setToasts] = useState<ToastItem[]>([]);

	const showToast = useCallback((message: string, type: ToastType = 'info') => {
		const id = Date.now() + Math.floor(Math.random() * 1000);
		setToasts((prev) => [...prev, { id, message, type }]);

		window.setTimeout(() => {
			setToasts((prev) => prev.filter((t) => t.id !== id));
		}, 3500);
	}, []);

	const value = useMemo(() => ({ showToast }), [showToast]);

	return (
		<ToastContext.Provider value={value}>
			{children}
			<div className="fixed top-4 right-4 z-[100] space-y-2 w-[min(360px,90vw)]">
				{toasts.map((toast) => (
					<div
						key={toast.id}
						className={`${styleByType[toast.type]} text-white rounded-lg shadow-lg px-4 py-3 text-sm`}
					>
						{toast.message}
					</div>
				))}
			</div>
		</ToastContext.Provider>
	);
}
