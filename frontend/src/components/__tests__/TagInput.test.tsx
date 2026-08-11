import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TagInput from '../TagInput';

describe('TagInput', () => {
	it('renders existing tags as chips', () => {
		const tags = ['react', 'typescript'];
		render(<TagInput tags={tags} onTagsChange={vi.fn()} />);

		expect(screen.getByText('react')).toBeInTheDocument();
		expect(screen.getByText('typescript')).toBeInTheDocument();
	});

	it('adds a tag on Enter key', () => {
		const handleChange = vi.fn();
		render(<TagInput tags={[]} onTagsChange={handleChange} />);

		const input = screen.getByPlaceholderText('Add tag...');
		fireEvent.change(input, { target: { value: 'vue' } });
		fireEvent.keyDown(input, { key: 'Enter' });

		expect(handleChange).toHaveBeenCalledWith(['vue']);
		expect(input).toHaveValue('');
	});

	it('removes a tag when × button is clicked', () => {
		const handleChange = vi.fn();
		render(<TagInput tags={['react', 'vue']} onTagsChange={handleChange} />);

		const removeButton = screen.getByLabelText('Remove tag react');
		fireEvent.click(removeButton);

		expect(handleChange).toHaveBeenCalledWith(['vue']);
	});

	it('shows autocomplete suggestions and selects on click', () => {
		const handleChange = vi.fn();
		const suggestions = ['react', 'redux', 'recoil', 'vue'];

		render(
			<TagInput
				tags={[]}
				onTagsChange={handleChange}
				suggestions={suggestions}
			/>
		);

		const input = screen.getByPlaceholderText('Add tag...');
		fireEvent.change(input, { target: { value: 're' } });

		// Suggestions dropdown should appear with matching items
		expect(screen.getByText('react')).toBeInTheDocument();
		expect(screen.getByText('redux')).toBeInTheDocument();
		expect(screen.getByText('recoil')).toBeInTheDocument();

		// Click a suggestion
		fireEvent.mouseDown(screen.getByText('redux'));

		expect(handleChange).toHaveBeenCalledWith(['redux']);
	});

	it('does not add duplicate tags', () => {
		const handleChange = vi.fn();
		render(<TagInput tags={['react']} onTagsChange={handleChange} />);

		const input = screen.getByPlaceholderText('Add tag...');
		fireEvent.change(input, { target: { value: 'react' } });
		fireEvent.keyDown(input, { key: 'Enter' });

		// onTagsChange should NOT be called — react is already a tag
		expect(handleChange).not.toHaveBeenCalled();
		// Input should still be cleared
		expect(input).toHaveValue('');
	});

	it('filters out already-selected tags from suggestions', () => {
		const suggestions = ['react', 'redux', 'vue'];
		render(
			<TagInput
				tags={['react']}
				onTagsChange={vi.fn()}
				suggestions={suggestions}
			/>
		);

		const input = screen.getByPlaceholderText('Add tag...');
		fireEvent.change(input, { target: { value: 're' } });

		// 'redux' should appear in the dropdown (as a <button>)
		expect(screen.getByText('redux')).toBeInTheDocument();

		// 'react' is already a tag - the chip renders as <span>, not a suggestion <button>
		// Check that there is no suggestion button with text 'react'
		const suggestionButtons = screen
			.getAllByRole('button')
			.filter(
				(btn) =>
					btn.textContent === 'react' &&
					btn.classList.contains('w-full')
			);
		expect(suggestionButtons).toHaveLength(0);
	});
});
