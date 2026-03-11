interface Props {
	isOpen: boolean;
	title: string;
	message: string;
	confirmLabel?: string;
	cancelLabel?: string;
	confirmStyle?: 'danger' | 'primary';
	onConfirm: () => void;
	onCancel: () => void;
}

export default function ConfirmDialog({
	isOpen,
	title,
	message,
	confirmLabel = 'Confirm',
	cancelLabel = 'Cancel',
	confirmStyle = 'primary',
	onConfirm,
	onCancel,
}: Props) {
	if (!isOpen) return null;

	const confirmButtonClass = confirmStyle === 'danger'
		? 'px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors'
		: 'px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors';

	return (
		<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
			<div className="bg-white rounded-lg shadow-xl max-w-md w-full">
				<div className="p-6">
					<h3 className="text-lg font-semibold text-gray-900 mb-2">
						{title}
					</h3>
					<p className="text-sm text-gray-600">
						{message}
					</p>
				</div>
				<div className="flex gap-3 p-6 pt-0">
					<button
						onClick={onCancel}
						className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50 transition-colors"
					>
						{cancelLabel}
					</button>
					<button
						onClick={onConfirm}
						className={confirmButtonClass}
					>
						{confirmLabel}
					</button>
				</div>
			</div>
		</div>
	);
}
