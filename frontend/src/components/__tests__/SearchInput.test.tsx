import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SearchInput from '../SearchInput';

describe('SearchInput', () => {
	it('renders with placeholder', () => {
		render(<SearchInput value="" onChange={vi.fn()} />);
		expect(screen.getByPlaceholderText('Search...')).toBeInTheDocument();
	});

	it('updates local value on typing and calls onChange after debounce', async () => {
		const handleChange = vi.fn();
		render(<SearchInput value="" onChange={handleChange} debounceMs={100} />);

		const input = screen.getByPlaceholderText('Search...');
		fireEvent.change(input, { target: { value: 'hello' } });

		// Local value should update immediately
		expect(input).toHaveValue('hello');

		// onChange should NOT be called yet (debounce)
		expect(handleChange).not.toHaveBeenCalled();

		// Wait for debounce
		await waitFor(
			() => {
				expect(handleChange).toHaveBeenCalledWith('hello');
			},
			{ timeout: 500 }
		);
	});

	it('shows clear button when value is non-empty and clears on click', () => {
		const handleChange = vi.fn();
		render(<SearchInput value="initial" onChange={handleChange} />);

		const input = screen.getByPlaceholderText('Search...');
		expect(input).toHaveValue('initial');

		// Clear button should be visible (SVG X icon within a button)
		const clearButton = input.parentElement!.querySelector('button');
		expect(clearButton).toBeInTheDocument();

		fireEvent.click(clearButton!);

		expect(input).toHaveValue('');
		expect(handleChange).toHaveBeenCalledWith('');
	});

	it('syncs local value when external value prop changes', () => {
		const handleChange = vi.fn();
		const { rerender } = render(
			<SearchInput value="first" onChange={handleChange} />
		);

		expect(screen.getByPlaceholderText('Search...')).toHaveValue('first');

		// External value changes
		rerender(<SearchInput value="second" onChange={handleChange} />);

		expect(screen.getByPlaceholderText('Search...')).toHaveValue('second');
	});

	it('applies custom placeholder', () => {
		render(
			<SearchInput
				value=""
				onChange={vi.fn()}
				placeholder="Find sources..."
			/>
		);

		expect(screen.getByPlaceholderText('Find sources...')).toBeInTheDocument();
	});
});
