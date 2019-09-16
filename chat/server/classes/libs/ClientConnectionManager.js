const SocketIO = require('socket.io');
const EventEmitter = require('events');
const ID_SIZE = 6
const Err = require("./IError.js");


/**
 * Manages client->island connections
 * adds and removes listeners
 * keeps track of active sockets
 */
class ClientConnectionManager extends EventEmitter{

    constructor(server = Err.required("Missing required parameter.")){
        super();
        this.io = SocketIO.listen(server);
        this.socketHub = this.io.of("/chat");
        this.dataSocketHub = this.io.of("/file");
        this.setListeners();
    }

    /**
     * Sets standard event handlers for
     */
    setListeners(){
        let self = this;
        self.socketHub.on('connection', (socket) => {
            self.emit("client_connected", socket.id);
            socket.on("disconnect", (reason)=>{
                console.log("Client disconnected: " + socket.id)
                self.emit("client_disconnected", socket.id)
            });

            socket.on('reconnect', (attemptNumber) => {
                self.emit("client_reconnected", socket.id)
            });
        });
        self.dataSocketHub.on('connection', (socket)=>{
            console.log("File socket connected");
            self.emit("data_channel_opened", socket);
            socket.on("disconnect", (reason)=>{
                self.emit("data_channel_closed", socket.id);
            });
            socket.on("reconnect",  (attemptNumber) => {
                self.emit("data_channel_reconnection", socket.id);
            })
        })
    }




    isSoskcetConnected(id){
        return (this.socketHub.sockets[id] && self.socketHub.sockets[id].connected);
    }

    getSocketById(id){
        if(!this.socketHub.sockets[id]){
            throw "Socket does not exist: " + id;
        }
        return this.socketHub.sockets[id];
    }

    getDataSocketById(id){
        if(!this.dataSocketHub.sockets[id]){
            throw "Socket does not exist: " + id;
        }
        return this.dataSocketHub.sockets[id];
    }




    sendError(connectionId, errMessage){
        this.send(connectionId, "error", errMessage);
    }

    sendResponse(connectionId, response){
        this.send(connectionId, "response", response);
    }

    sendRequest(connectionId, request){
        this.send(connectionId, "request", request);
    }

    sendServiceMessage(connectionId, message){
        this.send(connectionId, "service", message);
    }

    sendServiceRecord(connectionId, record){
        console.log("Sending service record");
        this.send(connectionId, "service_record", record);
    }

    sendChatMessage(connectionId, message){
        this.send(connectionId, "message", message);
    }

    /**
     *
     * @param message
     * @param data: arbitrary object
     * @param connectionId - translates to socketID
     */
    send(connectionId = Err.required("Missing required parameter connectionId"),
         message = Err.required("Missing required parameter message"),
         data = Err.required("Missing required parameter data")){
        let client = this.getSocketById(connectionId);
        if(!client || !client.connected){
            throw "Error sending message: client is not connected."
        }

        client.emit(message, data);
    }

}


module.exports = ClientConnectionManager;