import { Position } from './types';
/**
 * Get classic SVG path for a connection between two points.
 * @param points Array of two points
 * @param curvature Curvature of the connection
 */
export declare function classicConnectionPath(points: [Position, Position], curvature: number): string;
/**
 * Get loop SVG path for a connection between two points.
 * @param points Array of two points
 * @param curvature Curvature of the loop
 * @param size Size of the loop
 */
export declare function loopConnectionPath(points: [Position, Position], curvature: number, size: number): string;
//# sourceMappingURL=connection.d.ts.map