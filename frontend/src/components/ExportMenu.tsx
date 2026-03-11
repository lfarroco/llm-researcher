import { useState } from 'react';

interface Props {
	researchId: number;
	type: 'sources' | 'findings' | 'document';
	buttonText?: string;
	className?: string;
}

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export default function ExportMenu({ researchId, type, buttonText = 'Export', className = '' }: Props) {
	const [isOpen, setIsOpen] = useState(false);
	const [exporting, setExporting] = useState(false);

	const handleExport = async (format: string) => {
		setExporting(true);
		setIsOpen(false);

		try {
			let url = '';
			if (type === 'sources') {
				url = `${API_BASE}/research/${researchId}/export/sources/bibtex`;
			} else if (type === 'findings') {
				if (format === 'csv') {
					url = `${API_BASE}/research/${researchId}/export/findings/csv`;
				} else if (format === 'json') {
					url = `${API_BASE}/research/${researchId}/export/findings/json`;
				}
			} else if (type === 'document') {
				url = `${API_BASE}/research/${researchId}/export/${format}`;
			}

			// Special case for full data export
			if (format === 'data') {
				url = `${API_BASE}/research/${researchId}/export/data`;
			}

			const response = await fetch(url);
			if (!response.ok) {
				throw new Error('Export failed');
			}

			// Get filename from Content-Disposition header or generate one
			const contentDisposition = response.headers.get('Content-Disposition');
			let filename = `research_${researchId}_${type}_${format}`;
			if (contentDisposition) {
				const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(contentDisposition);
				if (matches && matches[1]) {
					filename = matches[1].replace(/['"]/g, '');
				}
			}

			// Download the file
			const blob = await response.blob();
			const downloadUrl = window.URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = downloadUrl;
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			window.URL.revokeObjectURL(downloadUrl);
			document.body.removeChild(a);
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Export failed');
		} finally {
			setExporting(false);
		}
	};

	const renderMenuItems = () => {
		if (type === 'sources') {
			return (
				<button
					onClick={() => handleExport('bibtex')}
					className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
				>
					BibTeX (.bib)
				</button>
			);
		} else if (type === 'findings') {
			return (
				<>
					<button
						onClick={() => handleExport('csv')}
						className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
					>
						CSV (.csv)
					</button>
					<button
						onClick={() => handleExport('json')}
						className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
					>
						JSON (.json)
					</button>
				</>
			);
		} else if (type === 'document') {
			return (
				<>
					<button
						onClick={() => handleExport('pdf')}
						className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
					>
						PDF (.pdf)
					</button>
					<button
						onClick={() => handleExport('html')}
						className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
					>
						HTML (.html)
					</button>
					<button
						onClick={() => handleExport('docx')}
						className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
					>
						Word (.docx)
					</button>
					<button
						onClick={() => handleExport('markdown')}
						className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
					>
						Markdown (.md)
					</button>
				</>
			);
		}
		return null;
	};

	return (
		<div className={`relative inline-block text-left ${className}`}>
			<button
				onClick={() => setIsOpen(!isOpen)}
				disabled={exporting}
				className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
			>
				{exporting ? (
					<>
						<svg className="animate-spin h-4 w-4 text-gray-600" fill="none" viewBox="0 0 24 24">
							<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
							<path
								className="opacity-75"
								fill="currentColor"
								d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
							/>
						</svg>
						Exporting...
					</>
				) : (
					<>
						<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
							/>
						</svg>
						{buttonText}
						<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
						</svg>
					</>
				)}
			</button>

			{isOpen && !exporting && (
				<>
					<div
						className="fixed inset-0 z-10"
						onClick={() => setIsOpen(false)}
						onKeyDown={(e) => e.key === 'Escape' && setIsOpen(false)}
						role="button"
						tabIndex={0}
						aria-label="Close menu"
					/>
					<div className="absolute right-0 z-20 mt-2 w-48 rounded-lg bg-white shadow-lg ring-1 ring-black ring-opacity-5">
						<div className="py-1" role="menu">
							{renderMenuItems()}
							{type !== 'document' && (
								<>
									<div className="border-t border-gray-200 my-1" />
									<button
										onClick={() => handleExport('data')}
										className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
									>
										Full Data (JSON)
									</button>
								</>
							)}
						</div>
					</div>
				</>
			)}
		</div>
	);
}
