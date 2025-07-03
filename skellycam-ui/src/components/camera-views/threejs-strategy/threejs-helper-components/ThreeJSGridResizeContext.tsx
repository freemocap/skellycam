import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';

// Define the grid cell interface
export interface GridCell {
    row: number;
    column: number;
    width: number;  // Relative width (0-1)
    height: number; // Relative height (0-1)
    x: number;      // Position x (0-1)
    y: number;      // Position y (0-1)
}

// Define the context interface
interface ThreeJSGridResizeContextType {
    gridCells: GridCell[];
    isDragging: boolean;
    activeHandleId: string | null;
    initializeGrid: (rows: number, columns: number) => void;
    startResizing: (handleId: string) => void;
    updateResize: (handleId: string, delta: number) => void;
    endResizing: () => void;
}

// Create the context
const ThreeJSGridResizeContext = createContext<ThreeJSGridResizeContextType | undefined>(undefined);

// Provider component
export function ThreeJSGridResizeProvider({ children }: { children: ReactNode }) {
    const [gridCells, setGridCells] = useState<GridCell[]>([]);
    const [isDragging, setIsDragging] = useState(false);
    const [activeHandleId, setActiveHandleId] = useState<string | null>(null);

    // Initialize grid with equal-sized cells
    const initializeGrid = useCallback((rows: number, columns: number) => {
        const cells: GridCell[] = [];
        const cellWidth = 1 / columns;
        const cellHeight = 1 / rows;

        for (let row = 0; row < rows; row++) {
            for (let column = 0; column < columns; column++) {
                cells.push({
                    row,
                    column,
                    width: cellWidth,
                    height: cellHeight,
                    x: column * cellWidth,
                    y: row * cellHeight
                });
            }
        }

        setGridCells(cells);
    }, []);

    // Start resizing
    const startResizing = useCallback((handleId: string) => {
        setIsDragging(true);
        setActiveHandleId(handleId);
    }, []);

    // Update during resize
    const updateResize = useCallback((handleId: string, delta: number) => {
        if (!isDragging || activeHandleId !== handleId) return;

        // Parse the handle ID to determine which cells to resize
        // Format: "h_row1_column1" for horizontal handle between row 1, column 1 and row 1, column 2
        // or "v_row1_column1" for vertical handle between row 1, column 1 and row 2, column 1
        const [direction, rowStr, columnStr] = handleId.split('_');
        const row = parseInt(rowStr.substring(3)); // Skip "row" prefix
        const column = parseInt(columnStr.substring(6)); // Skip "column" prefix

        setGridCells(prevCells => {
            // Create a copy of the cells
            const newCells = [...prevCells];

            if (direction === 'h') {
                // Horizontal handle - adjust width of cells in the same row
                const leftCell = newCells.find(cell => cell.row === row && cell.column === column);
                const rightCell = newCells.find(cell => cell.row === row && cell.column === column + 1);

                if (leftCell && rightCell) {
                    // Calculate new widths ensuring minimum size
                    const totalWidth = leftCell.width + rightCell.width;
                    const normalizedDelta = delta / totalWidth;

                    // Ensure minimum width (10% of original)
                    const minWidth = totalWidth * 0.1;

                    // Clamp delta to ensure minimum widths
                    const clampedDelta = Math.max(-leftCell.width + minWidth,
                        Math.min(rightCell.width - minWidth, normalizedDelta));

                    // Update widths
                    leftCell.width += clampedDelta;
                    rightCell.width -= clampedDelta;

                    // Update x positions for all cells to the right
                    newCells.forEach(cell => {
                        if (cell.row === row && cell.column > column) {
                            cell.x = newCells.filter(c => c.row === row && c.column < cell.column)
                                .reduce((sum, c) => sum + c.width, 0);
                        }
                    });
                }
            } else if (direction === 'v') {
                // Vertical handle - adjust height of cells in the same column
                const topCell = newCells.find(cell => cell.row === row && cell.column === column);
                const bottomCell = newCells.find(cell => cell.row === row + 1 && cell.column === column);

                if (topCell && bottomCell) {
                    // Calculate new heights ensuring minimum size
                    const totalHeight = topCell.height + bottomCell.height;
                    const normalizedDelta = delta / totalHeight;

                    // Ensure minimum height (10% of original)
                    const minHeight = totalHeight * 0.1;

                    // Clamp delta to ensure minimum heights
                    const clampedDelta = Math.max(-topCell.height + minHeight,
                        Math.min(bottomCell.height - minHeight, normalizedDelta));

                    // Update heights
                    topCell.height += clampedDelta;
                    bottomCell.height -= clampedDelta;

                    // Update y positions for all cells below
                    newCells.forEach(cell => {
                        if (cell.column === column && cell.row > row) {
                            cell.y = newCells.filter(c => c.column === column && c.row < cell.row)
                                .reduce((sum, c) => sum + c.height, 0);
                        }
                    });
                }
            }

            return newCells;
        });
    }, [isDragging, activeHandleId]);

    // End resizing
    const endResizing = useCallback(() => {
        setIsDragging(false);
        setActiveHandleId(null);
    }, []);

    return (
        <ThreeJSGridResizeContext.Provider
            value={{
                gridCells,
                isDragging,
                activeHandleId,
                initializeGrid,
                startResizing,
                updateResize,
                endResizing
            }}
        >
            {children}
        </ThreeJSGridResizeContext.Provider>
    );
}

// Custom hook to use the context
export function useThreeJSGridResize() {
    const context = useContext(ThreeJSGridResizeContext);
    if (context === undefined) {
        throw new Error('useThreeJSGridResize must be used within a ThreeJSGridResizeProvider');
    }
    return context;
}
