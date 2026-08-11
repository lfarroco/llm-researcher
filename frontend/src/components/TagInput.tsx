import { useState, useRef, useEffect } from 'react';

interface Props {
	tags: string[];
	onTagsChange: (tags: string[]) => void;
	suggestions?: string[];
	placeholder?: string;
}

export default function TagInput({
	tags,
	onTagsChange,
	suggestions = [],
	placeholder = 'Add tag...',
}: Props) {
	const [inputValue, setInputValue] = useState('');
	const [isDropdownOpen, setIsDropdownOpen] = useState(false);
	const [highlightedIndex, setHighlightedIndex] = useState(-1);
	const inputRef = useRef<HTMLInputElement>(null);
	const containerRef = useRef<HTMLDivElement>(null);

	// Filter suggestions: case-insensitive prefix match, exclude already-selected tags
	const filteredSuggestions = suggestions.filter(
		(s) =>
			s.toLowerCase().startsWith(inputValue.toLowerCase()) &&
			!tags.includes(s) &&
			s.trim().length > 0
	);

	const addTag = (tag: string) => {
		const trimmed = tag.trim();
		if (trimmed && !tags.includes(trimmed)) {
			onTagsChange([...tags, trimmed]);
		}
		setInputValue('');
		setHighlightedIndex(-1);
		setIsDropdownOpen(false);
		inputRef.current?.focus();
	};

	const removeTag = (tag: string) => {
		onTagsChange(tags.filter((t) => t !== tag));
	};

	const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === 'Enter') {
			e.preventDefault();
			// If a suggestion is highlighted, pick that; otherwise add typed text
			if (
				isDropdownOpen &&
				highlightedIndex >= 0 &&
				highlightedIndex < filteredSuggestions.length
			) {
				addTag(filteredSuggestions[highlightedIndex]);
			} else {
				addTag(inputValue);
			}
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			if (!isDropdownOpen && filteredSuggestions.length > 0) {
				setIsDropdownOpen(true);
				setHighlightedIndex(0);
			} else {
				setHighlightedIndex((prev) =>
					Math.min(prev + 1, filteredSuggestions.length - 1)
				);
			}
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			setHighlightedIndex((prev) => Math.max(prev - 1, -1));
		} else if (e.key === 'Escape') {
			setIsDropdownOpen(false);
			setHighlightedIndex(-1);
		}
	};

	const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		setInputValue(e.target.value);
		setIsDropdownOpen(true);
		setHighlightedIndex(-1);
	};

	const handleInputFocus = () => {
		if (filteredSuggestions.length > 0) {
			setIsDropdownOpen(true);
		}
	};

	// Close dropdown when clicking outside
	useEffect(() => {
		const handleClickOutside = (e: MouseEvent) => {
			if (
				containerRef.current &&
				!containerRef.current.contains(e.target as Node)
			) {
				setIsDropdownOpen(false);
				setHighlightedIndex(-1);
			}
		};
		document.addEventListener('mousedown', handleClickOutside);
		return () => document.removeEventListener('mousedown', handleClickOutside);
	}, []);

	return (
		<div ref={containerRef} className="relative">
			{/* Existing tags */}
			{tags.length > 0 && (
				<div className="flex flex-wrap gap-1.5 mb-2">
					{tags.map((tag) => (
						<span
							key={tag}
							className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded"
						>
							{tag}
							<button
								type="button"
								onClick={() => removeTag(tag)}
								className="text-blue-500 hover:text-blue-800 font-bold leading-none"
								aria-label={`Remove tag ${tag}`}
							>
								×
							</button>
						</span>
					))}
				</div>
			)}

			{/* Input */}
			<div className="flex gap-2">
				<input
					ref={inputRef}
					type="text"
					value={inputValue}
					onChange={handleInputChange}
					onKeyDown={handleInputKeyDown}
					onFocus={handleInputFocus}
					placeholder={placeholder}
					className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
				/>
				<button
					type="button"
					onClick={() => addTag(inputValue)}
					className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors text-sm"
				>
					Add
				</button>
			</div>

			{/* Autocomplete dropdown */}
			{isDropdownOpen && filteredSuggestions.length > 0 && (
				<div className="absolute left-0 right-0 mt-1 z-10 bg-white border border-gray-200 rounded shadow-lg max-h-48 overflow-y-auto">
					{filteredSuggestions.map((suggestion, index) => (
						<button
							key={suggestion}
							type="button"
							className={`w-full text-left px-3 py-1.5 text-sm ${
								index === highlightedIndex
									? 'bg-blue-50 text-blue-700'
									: 'text-gray-700 hover:bg-gray-50'
							}`}
							onMouseDown={(e) => {
								// onMouseDown fires before onBlur, preventing dropdown close
								e.preventDefault();
								addTag(suggestion);
							}}
							onMouseEnter={() => setHighlightedIndex(index)}
						>
							{suggestion}
						</button>
					))}
				</div>
			)}
		</div>
	);
}
