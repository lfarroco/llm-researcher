import { useState, useEffect } from 'react';

interface Props {
	value: string;
	onChange: (value: string) => void;
	placeholder?: string;
	debounceMs?: number;
	className?: string;
}

export default function SearchInput({
	value,
	onChange,
	placeholder = 'Search...',
	debounceMs = 300,
	className = '',
}: Props) {
	const [localValue, setLocalValue] = useState(value);

	// Update local value when external value changes
	useEffect(() => {
		setLocalValue(value);
	}, [value]);

	// Debounce the onChange callback
	useEffect(() => {
		const timer = setTimeout(() => {
			if (localValue !== value) {
				onChange(localValue);
			}
		}, debounceMs);

		return () => clearTimeout(timer);
	}, [localValue, debounceMs, onChange, value]);

	const handleClear = () => {
		setLocalValue('');
		onChange('');
	};

	return (
		<div className={`relative ${className}`}>
			<div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
				<svg
					className="h-5 w-5 text-gray-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeWidth={2}
						d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
					/>
				</svg>
			</div>
			<input
				type="text"
				value={localValue}
				onChange={(e) => setLocalValue(e.target.value)}
				placeholder={placeholder}
				className="block w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
			/>
			{localValue && (
				<button
					onClick={handleClear}
					className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
					type="button"
				>
					<svg
						className="h-5 w-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth={2}
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
				</button>
			)}
		</div>
	);
}
