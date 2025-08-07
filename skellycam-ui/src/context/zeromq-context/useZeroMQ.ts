
// skellycam-ui/src/context/zeromq-context/useZeroMQ.ts
import { useCallback, useEffect, useRef, useState } from "react";
import * as zmq from "zeromq";

export const useZeroMQ = (serverUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [connectAttempt, setConnectAttempt] = useState(0);
    const subscriberRef = useRef<zmq.Subscriber | null>(null);
    const publisherRef = useRef<zmq.Publisher | null>(null);
    const runningRef = useRef(false);

    // Connect to ZeroMQ server
    const connect = useCallback(async () => {
        if (runningRef.current) return;

        try {
            console.log(`Connecting to ZeroMQ server at: ${serverUrl}`);

            // Create subscriber for receiving images
            const subscriber = new zmq.Subscriber();
            await subscriber.connect(serverUrl);
            await subscriber.subscribe(""); // Subscribe to all topics
            subscriberRef.current = subscriber;

            // Create publisher for sending acknowledgments (on a different port)
            const ackPort = serverUrl.replace(/:(\d+)$/, ":5556"); // Use port 5556 for acks
            const publisher = new zmq.Publisher();
            await publisher.connect(ackPort);
            publisherRef.current = publisher;

            runningRef.current = true;
            setIsConnected(true);
            setConnectAttempt(0);

            console.log(`ZeroMQ connected to: ${serverUrl}`);

            // Start receiving messages
            receiveMessages();
        } catch (error) {
            console.error("ZeroMQ connection error:", error);
            runningRef.current = false;
            setIsConnected(false);
            setConnectAttempt(prev => prev + 1);

            // Clean up on error
            await disconnect();
        }
    }, [serverUrl]);

    // Disconnect from ZeroMQ server
    const disconnect = useCallback(async () => {
        runningRef.current = false;

        try {
            if (subscriberRef.current) {
                await subscriberRef.current.close();
                subscriberRef.current = null;
            }

            if (publisherRef.current) {
                await publisherRef.current.close();
                publisherRef.current = null;
            }

            setIsConnected(false);
            console.log("ZeroMQ disconnected");
        } catch (error) {
            console.error("ZeroMQ disconnect error:", error);
        }
    }, []);


    // Receive messages from ZeroMQ
    const receiveMessages = useCallback(async () => {
        if (!subscriberRef.current || !runningRef.current) return;

        try {
            // Use for-await loop to receive messages
            for await (const [topic, frameNumber, payload] of subscriberRef.current) {
                if (!runningRef.current) break;

                try {

                    console.log(`Received message on topic: ${topic.toString()}, frame: ${frameNumber.toString()} payload size: ${payload.length}`);

                } catch (error) {
                    console.error("Error processing ZeroMQ message:", error);
                }
            }
        } catch (error) {
            console.error("ZeroMQ receive error:", error);
            runningRef.current = false;
            setIsConnected(false);
            setConnectAttempt(prev => prev + 1);
        }
    }, []);

    // Auto-reconnect with exponential backoff
    useEffect(() => {
        if (isConnected) return;

        const timeout = setTimeout(() => {
            console.log(
                `Connecting to ZeroMQ server at: ${serverUrl} (attempt #${connectAttempt + 1})`
            );
            connect();
        }, Math.min(1000 * Math.pow(2, connectAttempt), 10000)); // exponential backoff

        return () => {
            clearTimeout(timeout);
        };
    }, [connect, connectAttempt, serverUrl, isConnected]);

    // Clean up on unmount
    useEffect(() => {
        return () => {
            disconnect();
        };
    }, [disconnect]);

    return {
        isConnected,
        connect,
        disconnect,
    };
};
