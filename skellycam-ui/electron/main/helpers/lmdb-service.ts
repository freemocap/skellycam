// electron/main/helpers/lmdb-service.ts
import {Database, open, RootDatabase} from "lmdb";
import path from "node:path";
import {app} from "electron";
import os from "node:os";
import fs from "node:fs";

// Interfaces for the configuration
interface LmdbSchemaConfig {
    keyFormat: string;
    valueFormat: string;
}

interface LmdbConfig {
    dbPath: string;
    mapSize: number;
    maxDbs: number;
    compression: boolean;
    schemas: {
        [key: string]: LmdbSchemaConfig;
    };
}

export class LmdbService {
    private db: RootDatabase | null = null;
    private dbs: { [key: string]: Database } = {};
    public dbPath: string;
    private config: LmdbConfig;

    constructor(
        configPath: string = path.join(
            app.getAppPath(),
            "../shared/skellycam_lmdb_config.json"
        )
    ) {
        // Load configuration from JSON file
        try {
            const configData = fs.readFileSync(configPath, "utf8");
            this.config = JSON.parse(configData);
        } catch (error) {
            console.error(
                `Failed to load LMDB configuration from ${configPath}:`,
                error
            );
            throw new Error("Failed to load LMDB configuration");
        }

        // Resolve the database path from the configuration
        const homeDir = os.homedir();
        // Normalize path with proper platform-specific separators
        this.dbPath = path.normalize(this.config.dbPath.replace("~", homeDir));
        console.log(`LMDB database path: ${this.dbPath}`);
    }

    initialize(): boolean {
        try {
            // Create the directory if it doesn't exist
            if (!fs.existsSync(this.dbPath)) {
                fs.mkdirSync(this.dbPath, {recursive: true});
            }

            this.db = open({
                path: this.dbPath,
                mapSize: this.config.mapSize,
                maxDbs: this.config.maxDbs,
                compression: this.config.compression,
            });

            // Open named databases based on schema config
            for (const [dbName, schema] of Object.entries(this.config.schemas)) {
                this.dbs[dbName] = this.db.openDB({name: dbName});
            }

            console.log(`LMDB database initialized at: ${this.dbPath}`);
            return true;
        } catch (error) {
            console.error("Failed to initialize LMDB:", error);
            return false;
        }
    }

    get<T>(dbName: string, key: string): T | null {
        try {
            if (!this.db || !this.dbs[dbName])
                throw new Error(`Database ${dbName} not initialized`);
            return this.dbs[dbName].get(key) as T;
        } catch (error) {
            console.error(`Error getting key ${key} from ${dbName}:`, error);
            return null;
        }
    }

    async put<T>(dbName: string, key: string, value: T): Promise<boolean> {
        try {
            if (!this.db || !this.dbs[dbName])
                throw new Error(`Database ${dbName} not initialized`);
            await this.dbs[dbName].put(key, value);
            return true;
        } catch (error) {
            console.error(`Error putting key ${key} to ${dbName}:`, error);
            return false;
        }
    }

    async remove(dbName: string, key: string): Promise<boolean> {
        try {
            if (!this.db || !this.dbs[dbName])
                throw new Error(`Database ${dbName} not initialized`);
            await this.dbs[dbName].remove(key);
            return true;
        } catch (error) {
            console.error(`Error removing key ${key} from ${dbName}:`, error);
            return false;
        }
    }

    listKeys(dbName: string, prefix?: string): string[] {
        try {
            if (!this.db || !this.dbs[dbName])
                throw new Error(`Database ${dbName} not initialized`);

            const keys: string[] = [];
            for (const key of this.dbs[dbName].getKeys()) {
                if (prefix && !key.toString().startsWith(prefix)) continue;
                keys.push(key.toString());
            }
            return keys;
        } catch (error) {
            console.error(`Error listing keys from ${dbName}:`, error);
            return [];
        }
    }

    close(): void {
        try {
            if (this.db) {
                this.db.close();
                this.db = null;
                this.dbs = {};
                console.log("LMDB database closed");
            }
        } catch (error) {
            console.error("Error closing database:", error);
        }
    }
}

// Create a singleton instance
export const lmdbService = new LmdbService();
