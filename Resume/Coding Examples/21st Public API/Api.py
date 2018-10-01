import datetime
from functools import wraps
#Flask extensions
from flask import Flask, jsonify, request
from flask_restful import Api, Resource, reqparse
from flaskext.mysql import MySQL
#pusher extensions
import pusher
from pusher_push_notifications import PushNotifications
#twilio extensions
from twilio.rest import Client
from flask_sslify import SSLify

app = Flask(__name__)
sslify = SSLify(app)

#sql database parameters
mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = ''
app.config['MYSQL_DATABASE_PASSWORD'] = ''
app.config['MYSQL_DATABASE_DB'] = ''
app.config['MYSQL_DATABASE_HOST'] = ''
mysql.init_app(app)
privateNotificationTable = ""

#twilio account info
account_sid = ""
auth_token = ""

#twilio numbers
outgoingNumber = ''
williesNumber = ''

#authorization login
auth_username = ""
auth_password = ""

#admin Auth key
api_admin_auth = ""

#interests for pusher
interests = ''

#keys for pusher
pusher_instance_id="",
pusher_secret_key="",

#check for valid username password combo
def check_auth(username, password):
    return username == auth_username and password == auth_password

#Sends a 401 response that enables basic auth
def authenticate():
    return "invalid auth credentials", 401

#Method that checks for proper authorization to access an endpoint
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        print(auth)
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

api = Api(app)

class Notification(Resource):
    #Make a get request for a notification with a specific notificationID (notID)
    @requires_auth
    def get(self, notID):
        try:
            cursor = mysql.connect().cursor()
            parser = reqparse.RequestParser()
            parser.add_argument('secretKey', location='headers')
            parser.add_argument('isPosted', location='headers')
            args = parser.parse_args()
            response = helpMethods.notificationExsists(notID, args['isPosted'])
            doesExsist = response[0]
            result = response[1]

            #check to see if notification exsists in Database
            if(doesExsist):
                content = {'id': result[0], 'date' : str(result[1]), 'message': result[2], 'sourceLink': result[3], 'userID':result[4]}
                return content, 201
            else:
                return "No notifications matching the given parameters", 204

        except Exception as e:
            print(e)
            return "Server Error", 500

    #publically post a notification that was private
    @requires_auth
    def post(self, notID):
        try:
            parser = reqparse.RequestParser(bundle_errors=True)
            parser.add_argument("secretKey", location='headers', help = 'problem with secretKey paramater')
            args = parser.parse_args()
            mysqlConnection = mysql.connect()
            cursor = mysqlConnection.cursor()

            #check to make sure user has permission to post
            if helpMethods.checkForAuthorization(args):
                response = helpMethods.notificationExsists(notID, 'false')
                doesExsist = response[0]
                if(doesExsist):
                    query = "update table {0} where notificaitonID = {1} set posted = 'True'".format(privateNotificationTable, notID)
                    cursor.execute(query)
                    mysqlConnection.commit()
                    cursor.close()
                    #send IOS notification
                    helpMethods.sendNotification(response["message"],interests)
                    return "notification successufully posted publically", 201
                else:
                    cursor.close()
                    return 'notification with given ID either is already public or does not exsist', 204
            else:
                cursor.close()
                return "Invalid API key", 401

        except Exception as e:
            print(e)
            return "Server Error", 500

    #delete notification with given notificationID
    @requires_auth
    def delete(self, notID):
        try:
            mysqlConnection = mysql.connect()
            cursor = mysqlConnection.cursor()
            parser = reqparse.RequestParser()
            parser.add_argument('secretKey', location='headers')
            parser.add_argument('isPosted', location='headers')
            args = parser.parse_args()

            if helpMethods.checkForAuthorization(args):
                response = helpMethods.notificationExsists(notID, args['isPosted'])
                doesExsist = response[0]
                result = response[1]

                #check to see if notification exsists in Database
                if(doesExsist):
                    query = ("delete from " + privateNotificationTable + " where notificationID = " + notID + " and posted = \'{0}\'".format(result[5]) )
                    cursor.execute(query)
                    mysqlConnection.commit()
                    cursor.close()
                    return "Notification Successufully Deleted", 201
                else:
                    return "No notifications matching the given parameters", 203
            else:
                return "Invalid Admin Key", 401

        except Exception as e:
            print(e)
            return "Server error", 500

class NotificationAuto(Resource):
    #get a set of the most recent notifcations that have been posted publically
    @requires_auth
    def get(self):
        #Past number of notiifcations to display
        numNotificiations = 10
        try:
            cursor = mysql.connect().cursor()
            parser = reqparse.RequestParser()
            parser.add_argument('secretKey', location='headers')
            args = parser.parse_args()
            query = "  select * from {0} where posted = 'True' order by notificationID desc LIMIT {1};".format(privateNotificationTable, numNotificiations)
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            responseJson = {}
            i = 0
            for notification in results:
                responseJson[i] = helpMethods.jsonifySQLResponse(results[i])
                i += 1
            return responseJson, 201

        except Exception as e:
            print(e)
            return "Server Error", 500

    #post a notification either publically or privately
    @requires_auth
    def post(self):
        try:
            mysqlConnection = mysql.connect()
            cursor = mysqlConnection.cursor()
            args = helpMethods.getPostArgs()
            query = "Insert Into {0}(message, sourceLink, UserID, posted) values(\'{1}\',\"{2}\", \"{3}\", \"{4}\")".format(privateNotificationTable, args["message"], args["sourceLink"], args["userID"], args["isPosted"])
            #check to see if notification exsists in Database
            cursor.execute(query)
            mysqlConnection.commit()
            cursor.close()

            if(args["isPosted"] == 'True'):
                if helpMethods.checkForAuthorization(args):
                    #send notification
                    helpMethods.sendNotification(args["message"], interests)
                    return 'Notification successfully posted publically', 201
                else:
                    return "Invalid admin key", 401
            else:
                #sendText
                message = args["userID"] + ": " + args["message"]
                helpMethods.sendText(message, williesNumber)
            return "notification successufully posted on privately", 201

        except Exception as e:
            print(e)
            return "Server Error", 500

class helpMethods(object):
    #method to determine if a notification with a given ID already exsists
    @staticmethod
    def notificationExsists(notID, isPosted):
        cursor = mysql.connect().cursor()
        query = ('SELECT * from ' + privateNotificationTable + ' where notificationID = ' + notID + ' and posted = \'{0}\''.format(isPosted))
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        if(result != None):
            return ( True , result )
        else:
            return ( False , False )

    #sends IOS notification to subscribed devices with given message
    @staticmethod
    def sendNotification(message, targetInterests):
        try:
            #pusher instance
            pn_client = PushNotifications(
                instance_id="e26036a3-7c7e-4de1-a782-a8aee792f3c4",
                secret_key="AE5D352C43A1139E2587312C231A478",
                )
            #send notification
            response = pn_client.publish(
                interests=['hello'],
                publish_body={
                    'apns': {
                        'aps': {
                            'alert':message
                                },
                            },
                        },
                    )

        except Exception as e:
            print("error while trying to send notification. Error: " + str(e))
            return "error while trying to send notification. Error: " + str(e), 200

    #Sends text message to Admin devices with given message
    @staticmethod
    def sendText(message, targetNumber):
        twilClient = Client(account_sid, auth_token)
        message = twilClient.messages.create(
              from_=outgoingNumber,
              body=message,
              to= williesNumber,
          )

    #Creates standardized notification JSON object with given args
    @staticmethod
    def createNotificationJSON(args):
            #create JSON object of notification
            notification = {
                "notID": notID,
                "date": date.today(),
                "message": args["message"],
                "sourceLink": args["sourceLink"],
                "userID":args["userID"],
                "isPosted":args["isPosted"],
                "adminKey":args["adminKey"]
            }
            #make sure valid isPosted value
            if(notification['isPosted'] != 'True' and notification['isPosted'] != 'true'):
                notification['isPosted'] = 'false'
            return notification

    #creates standardizes JSON notification object from SQL query 
    @staticmethod
    def jsonifySQLResponse(result):
        try:
            content = {'id': result[0], 'date' : result[1].strftime('%m/%d/%Y'), 'message': result[2], 'sourceLink': result[3], 'userID':result[4], 'isPosted':result[5]}
            return content

        except Exception as e:
            content = {'id': "No ID", 'date' : 'No Date', 'message': 'No Message', 'sourceLink': 'No Source Link', 'userID': 'No User Id', 'isPosted' : 'False'}
            print("invalid SQL response Error: " + str(e))
            return content

    @staticmethod
    def getPostArgs():
        parser = reqparse.RequestParser(bundle_errors=True)
        parser.add_argument("message", help = 'problem with message paramater')
        parser.add_argument("sourceLink", help = 'problem with sourceLink paramater')
        parser.add_argument("userID", help = 'problem with userID paramater')
        parser.add_argument("secretKey", location='headers', help = 'problem with secretKey paramater')
        parser.add_argument("isPosted", location='headers', help = 'problem with isPosted paramater')
        parser.add_argument("adminKey", location='headers', help = 'problem with adminKey paramater')
        args = parser.parse_args()
        return args

    #Checks for valid authorization
    @staticmethod
    def checkForAuthorization(args):
        adminKey = args["adminKey"]
        if adminKey == api_admin_auth:
            return True
        else:
            return False

api.add_resource(Notification, "/notification/<string:notID>")
api.add_resource(NotificationAuto, "/notification/")
