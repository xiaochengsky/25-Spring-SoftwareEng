from flask import Flask, request, abort, jsonify
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from pubsub import pub
from TxDefi.Data.WebMessage import WebMessage
from TxDefi.Data.Factories import WebMessageFactory
from TxDefi.Abstractions.AbstractQueueProcessor import AbstractQueueProcessor

#Used to listen to data from a web hook server
class WebhookServer(AbstractQueueProcessor[WebMessage]):
    def __init__(self, webhook_name: str, listen_port: int, pub_topic_name: str, ed_encription_pubkey: str = None):
        AbstractQueueProcessor.__init__(self)

        self.app = Flask(__name__)

        if not ed_encription_pubkey:
            self.verify_key = None
        else:
            try:      
                self.verify_key = VerifyKey(bytes.fromhex(ed_encription_pubkey))
            except Exception as e:
                self.verify_key = None

        self.pub_topic_name = pub_topic_name
        self.listen_port = listen_port

        self.app.add_url_rule('/'+ webhook_name, 'handle_webhook', self.handle_webhook, methods=['POST'])

    def init_processor(self):
        self.app.run(threaded=False, port=self.listen_port)

    def process_message(self, message: WebMessage):
        #Notify topic subs
        pub.sendMessage(topicName=self.pub_topic_name, arg1=message)
            
    def handle_webhook(self):
        data = request.json
        print("Webhook Received: " + str(data))
        payload_type = data.get('type')

        if self.is_xsignature_request(request):
            is_valid = self.verify_xsignature_request(request)

            if is_valid:
                return jsonify({"type": 1}), 200  #
            else:
                abort(401, 'invalid request signature')
        elif payload_type == 0:
            return jsonify({"type": 1}), 204
        else:
            web_message = WebMessageFactory.create_web_message(data)

            if web_message:
                self.message_queue.put_nowait(web_message)
 
            return {"status": "success"}, 200

    def stop(self):
        pass
    
    #FYI this Discord stuff below is not really necessary right now; we're using the bot gateway to receive channel messages
    #See DiscordMonitor
    @staticmethod
    def is_xsignature_request(request):
        return request.headers.get("X-Signature-Ed25519") and request.headers.get("X-Signature-Timestamp")

    def verify_xsignature_request(self, request):
        verify_succeeded = False
        signature = request.headers.get("X-Signature-Ed25519")
        timestamp = request.headers.get("X-Signature-Timestamp")

        if signature and timestamp:
            """
            Verify the Discord request using Ed25519.
            :param signature: The value from X-Signature-Ed25519 header
            :param timestamp: The value from X-Signature-Timestamp header
            :param body: The raw request body (bytes)
            """
            try:                
                # Get raw request body
                body = request.data.decode("utf-8")

                self.verify_key.verify(f'{timestamp}{body}'.encode(), bytes.fromhex(signature))
                verify_succeeded = True
            except BadSignatureError:
                verify_succeeded = False

        return verify_succeeded