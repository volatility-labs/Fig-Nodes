import { LGraph, LGraphCanvas } from '@comfyorg/litegraph';
import { DialogManager } from './DialogManager';
import { LinkModeManager } from './LinkModeManager';
import { FileManager } from './FileManager';
import { APIKeyManager } from './APIKeyManager';
import { AppState } from './AppState';
import { ExecutionStatusService } from './ExecutionStatusService';

export interface ServiceMap {
    graph: LGraph;
    canvas: LGraphCanvas;
    dialogManager: DialogManager;
    linkModeManager: LinkModeManager;
    fileManager: FileManager;
    apiKeyManager: APIKeyManager;
    appState: AppState;
    statusService: ExecutionStatusService;
}

export type ServiceName = keyof ServiceMap;

export class ServiceRegistry {
    private services = new Map<ServiceName, ServiceMap[ServiceName]>();

    register<K extends ServiceName>(name: K, service: ServiceMap[K]): void {
        this.services.set(name, service);
    }

    get<K extends ServiceName>(name: K): ServiceMap[K] | null {
        const service = this.services.get(name);
        return service as ServiceMap[K] | null;
    }

    // Allow weak get for untyped access in fallbacks
    getAny(name: string): unknown | null {
        return (this.services as any).get(name) ?? null;
    }

    has(name: ServiceName): boolean {
        return this.services.has(name);
    }

    unregister(name: ServiceName): void {
        this.services.delete(name);
    }

    clear(): void {
        this.services.clear();
    }

    getAllServices(): Partial<ServiceMap> {
        const result: Partial<ServiceMap> = {};
        for (const [key, value] of this.services) {
            (result as Record<string, unknown>)[key] = value;
        }
        return result;
    }
}
