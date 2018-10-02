"""
@author: Tyler Williams
For use with the MPSCARA
Tested in, developed for, and funded by the Solheim Additive 
Manufacturing Laboratory at the University of Washington, Seattle.

REQUIRES
settings.txt
    Contains:
        Machine Name:XXXX
        L1 (mm, measured on printed part):XXX.XX
        L2 (mm, measured on printed part):XXX.XX
        Inner Radius limit (mm, usually 90 for left handed):XX
        Handed (R/L):L
        Quality (Interpolation length, mm):2
        Max Speed [deg/min]:1400
    For quality, lower number = straighter output lines = larger file size
targets.txt 
    Contains:
        g_code_file_1.g
        g_code_file_2.gcode
        ...
    [etc, can process any number of files, list all names here]
Special thanks to Andreas Bru, Professor Mark Ganter, and the 2018 
Spring Class of ME 480 at the University of for bug-catching and bug-fixing
"""
import math
import sys
import re

def stripComments(code):
    return re.sub(r';.*\n?', '', code)

try:
    s = open("settings.txt","r")
except:
    sys.exit("File 'settings.txt' is missing, please read included "+
             "instructions and try again")
try:
    t = open("targets.txt","r")
except:
    sys.exit("File 'targets.txt' is missing, please read included "+
             "instructions and try again")
settings = s.readlines()
i=0
for line in settings:
    settings[i] = line[line.index(":")+1:-1]
    i+=1
targets = t.readlines()
m_name = str(settings[0]).strip()
quality = float(settings[5])


# Converts the linear feedrate from mm/min to deg/min, and scales
# based on location. x1, y1 are the initial coordinates, x2, y2 are the end
# coordinates, F is the linear feedrate, settings contains the settings for
# the machine.
def find_feedrate(x1,x2,y1,y2,F,settings):
    a = float(settings[1]) # Length of the upper arm/vector a
    b = float(settings[2]) # Length of the forearm/vector b
    handed = str(settings[4]).upper().strip()
    if handed == "R":
        h = -1
    else:
        h = 1
    dist = math.sqrt((x2-x1)**2+(y2-y1)**2) # Distance between the two coords.
    if dist != 0:
        x_dot = (x2-x1)/dist*F # Linear velocity in the x direction
        y_dot = (y2-y1)/dist*F # Linear velocity in the y direction
        c = math.sqrt(x1**2+y1**2) # Length of vector C (From shoulder to coord 1)
        c_dot = (x1*x_dot+y1*y_dot)/math.sqrt(x1**2+y1**2) # Rate of change of the 
                                                           # length of vector c
        omega_c = (x1*y_dot-y1*x_dot)/c**2 # Angular rate of change of vector c
        omega_a = (omega_c - h*c_dot*(2*c**2*a-c**2-a**2+b**2)/(2*c**2*a**2)*
                  math.sqrt(1-(c**2+a**2-b**2)/(2*c*a))) # Angular rate of change 
                                                         # of the upper arm
        omega_b = (omega_c + h*c_dot*(2*c**2*b-c**2-b**2+a**2)/(2*c**2*b**2)*
                  math.sqrt(1-(c**2+b**2-a**2)/(2*c*b))) # Angular rate of change
                                                         # of the forearm
        omega = math.sqrt(omega_a**2+omega_b**2) # Sum the squares of the angular
                                                 # feedrates.
    else:
        omega = 0
    return min(abs(round(math.degrees(omega),5)),float(settings[6]))

# Determines the required angles of each motor in order to set the end
# at the proper position. x,y are the coordinates in the cartesian system,
# settings contains the settings of the machine, and name is the name of the
# gcode file being analyzed.
def find_angles(x,y,settings,file_name):
    a = float(settings[1])
    b = float(settings[2])
    handed = str(settings[4]).upper().strip()
    c = math.sqrt(x**2+y**2)
    thetaC = math.atan2(y,x)
    if handed == "R":
        h = -1
    else:
        h = 1
    try:
        thetaA = thetaC + h * math.acos((c**2 + a**2 - b**2)/(2*c*a))
        thetaB = thetaC - h * math.acos((c**2 + b**2 - a**2)/(2*c*b))
    except:
        sys.exit("File '%s.g' attempts to go outside of build area,"%file_name
                 + " please resize or rearrange and try again.")
    return[round(math.degrees(thetaA),4),round(math.degrees(thetaB),4)]

"""
This goes through every name posted in the targets file and creates a
new file with the _MPSCARA suffix.  It then populates the file with the
angular g-code, cutting the line segments into pieces [QUALITY] long
and producing additional points as needed in order to approximate lines
from large numbers of small arcs.  It also calls the find_feedrate
function to properly set the angular feedrates from the given linear
feedrates, and does this at the beginning of each segment.  As expected
a lower [QUALITY] value will cut the line segments into more pieces,
producing larger numbers of smaller arcs that will better approximate
straight lines, but this can lead to joltier movements, and greatly
increases .g file sizes.
"""
for file_name in targets:
    inner_rad = float(settings[3])
    gn = str(file_name)
    if gn.endswith("\n"):
        # Trims new-line characters
        gn = gn[:-1]
    if gn.endswith(".gcode"):
        # Trims the .gcode suffix to get the file name
        gn = gn[:-6]
    elif gn.endswith(".g"):
        # Trims the .g suffix to get the file name
        gn = gn[:-2]
    old_g = open(gn + ".g" ,"r")
    new_g = open(gn + "_MPSCARA.g","w+")
    new_g.write("; Translated for use with the MPSCARA Machine %s\n"%m_name)
    new_g.write("; File Quality: %d mm\n"%quality)
    x_old = None    # Initializing x position variable
    y_old = None    # Initializing y position variable
    e_old = None    # Initializing extruder position variable
    f = None        # Initializing feedrate variable
    for line in old_g:
        line = stripComments(line)
        arguments = line.upper().split()
        if line.upper().startswith("G92 "):
            # Catches variable resets, usually only useful for E value.
            for coord in arguments:
                if coord.upper().startswith("X"):
                    x_old = 0
                elif coord.upper().startswith("Y"):
                    y_old = 0
                elif coord.upper().startswith("Z"):
                    z_old = 0
                elif coord.upper().startswith("E"):
                    e_old = 0
        if line.upper().startswith("G0 ") or line.upper().startswith("G1 ") or line.upper().startswith("G01 ") or line.upper().startswith("G00 "):
            x_new = None
            y_new = None
            z_new = None
            e_new = None
            for coord in arguments:
                # Goes through the gcode line and stores important values
                if coord.upper().startswith("X"):
                    x_new = float(coord[1:].strip())
                elif coord.upper().startswith("Y"):
                    y_new = float(coord[1:].strip())+inner_rad
                    # The y offset is added in here for clarity in future
                    # calculations.
                elif coord.upper().startswith("Z"):
                    z_new = float(coord[1:].strip())
                elif coord.upper().startswith("E"):
                    e_new = float(coord[1:].strip())
                elif coord.upper().startswith("F"):
                    f = float(coord[1:].strip())
            if x_new == None and y_new == None:
                code_line = arguments[0] + " "
                if z_new != None:
                    code_line += "Z%f "%z_new
                if e_new != None:
                    code_line += "E%f "%e_new
                if f != None:
                    code_line += "F%f "%f
            elif x_old == None and y_old == None:
                [thetaA,thetaB] = find_angles(x_new,y_new,settings,gn)
                code_line = "G1 X%f Y%f "%(thetaA, thetaB)
                if z_new != None:
                    code_line += "Z%f "%z_new
                if e_new != None:
                    code_line += "E%f "%e_new
                if f != None:
                    code_line += "F%f "%f
            else:
                if x_new == None:
                    x_new = x_old
                if y_new == None:
                    y_new = y_old
                x_mid = x_old
                y_mid = y_old
                e_mid = e_old
                movement = math.sqrt((x_new-x_mid)**2+(y_new-y_mid)**2)
                while movement > quality:
                    x_mid = x_mid + (x_new - x_mid)*quality/movement
                    y_mid = y_mid + (y_new - y_mid)*quality/movement
                    if e_new != None and e_mid != None:
                        e_mid = round(e_mid + (e_new - e_mid)
                                      *quality/movement,6)
                    [thetaA,thetaB] = find_angles(x_mid,y_mid,settings,gn)
                    code_line = "G1 X%f Y%f "%(thetaA, thetaB)
                    if z_new != None:
                        code_line += "Z%f "%z_new
                    if e_mid != None:
                        code_line += "E%f "%e_mid
                    if f != None:
                        omega = find_feedrate(x_mid,x_new,y_mid,
                                              y_new,f,settings)
                        code_line += "F%f "%omega
                    new_g.write(code_line.strip() + "\n")    
                    movement = math.sqrt((x_new-x_mid)**2+(y_new-y_mid)**2)
                [thetaA,thetaB] = find_angles(x_new,y_new,settings,gn)
                code_line = "G1 X%f Y%f "%(thetaA, thetaB)
                if z_new != None:
                    code_line += "Z%f "%z_new
                if e_new != None:
                    code_line += "E%f "%e_new
                if f != None:
                    omega = find_feedrate(x_mid,x_new,y_mid,y_new,f,settings)
                    code_line += "F%f "%omega
            if x_new != None:
                x_old = x_new
            if y_new != None:
                y_old = y_new
            if e_new != None:
                e_old = e_new
            new_g.write(code_line.strip() + "\n")
        else:
            new_g.write(line.strip() + "\n")
    new_g.close()
