// electron/main/helpers/lmdb-service.ts
import { open, RootDatabase } from 'lmdb';
import path from 'node:path';
import { app } from 'electron';
import os from 'node:os';
import fs from 'node:fs';

export class LmdbService {
    private db: RootDatabase | null = null;
    public dbPath: string;

    constructor(dbName: string = 'skellycam_lmdb') {
        // Use user's home directory + skellycam_data folder
        const homeDir = os.homedir();
        const dataDir = path.join(homeDir, 'skellycam_data');

        // Create the directory if it doesn't exist
        if (!fs.existsSync(dataDir)) {
            fs.mkdirSync(dataDir, { recursive: true });
        }

        this.dbPath = path.join(dataDir, dbName);
        console.log(`LMDB database path: ${this.dbPath}`);
    }

    initialize(): boolean {
        try {
            this.db = open({
                path: this.dbPath,
                compression: true,
            });
            console.log(`LMDB database initialized at: ${this.dbPath}`);
            return true;
        } catch (error) {
            console.error('Failed to initialize LMDB:', error);
            return false;
        }
    }

    get<T>(key: string): T | null {
        try {
            if (!this.db) throw new Error('Database not initialized');
            return this.db.get(key) as T;
        } catch (error) {
            console.error(`Error getting key ${key}:`, error);
            return null;
        }
    }

    async put<T>(key: string, value: T): Promise<boolean> {
        try {
            if (!this.db) throw new Error('Database not initialized');
            await this.db.put(key, value);
            return true;
        } catch (error) {
            console.error(`Error putting key ${key}:`, error);
            return false;
        }
    }

    async remove(key: string): Promise<boolean> {
        try {
            if (!this.db) throw new Error('Database not initialized');
            await this.db.remove(key);
            return true;
        } catch (error) {
            console.error(`Error removing key ${key}:`, error);
            return false;
        }
    }

    close(): void {
        try {
            if (this.db) {
                this.db.close();
                this.db = null;
                console.log('LMDB database closed');
            }
        } catch (error) {
            console.error('Error closing database:', error);
        }
    }
}

// Create a singleton instance
export const lmdbService = new LmdbService();
