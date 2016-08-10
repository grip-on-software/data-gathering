#!/bin/bash

# Define properties #########################
DATE_REGEXP="[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}"
EXTRACT_FIRST_NUMBER="s/^[^0-9]*\([0-9]\+\).*$/\1/"
IS_NUMBER="^[0-9]+$"

# Store info for execution control of this script
RECURSIVE_CALL="$0 $*"
SCRIPT=`basename $0`
QUIET=0
DELTA=4

# Check command line argument ###############
read -d '' USAGE <<- EOF
	Usage:
	$SCRIPT [--once] [--delta <n>] [--quiet [--quiet]] <project>

	--once             - run once (not continuously)
	--delta <n>        - skip <n> days to check for newer history (n > 0, default: 4)
	--quiet            - show info (no debug) messages
	--quiet --quiet    - show only warnings and errors
	
	For example: $SCRIPT --once lrk
EOF
while [ "$1" != "" ] ; do
	case $1 in
		--once )	RECURSIVE_CALL=
				;;
		--delta )	shift
				if [[ "$1" =~ "$IS_NUMBER" ]]; then
					DELTA="$1"
				else
					echo -e "$USAGE"
					exit 1
				fi
				;;
		--quiet )	QUIET=`expr $QUIET + 1`
				;;
		* )		if [ "$PROJECT" != "" ]; then
					echo -e "$USAGE"
					exit 1
				fi
				PROJECT=$1
	esac
	shift
done

# Stop if no project is specified
if [ "$PROJECT" == "" ]; then
	echo -e "$USAGE"
	exit 1
fi

# Stop if quiet is used too often
if [ "$QUIET" -gt "2" ]; then
	echo -e "$USAGE"
	exit 1
fi

# Stop if delta is 0
if [ "$DELTA" == "0" ]; then
	echo -e "$USAGE"
	exit 1
fi

# Perform operations ########################

# Check which history file already exists
SVN_HISTORY_FILE=https://SUBVERSION_SERVER.localhost/commons/algemeen/kwaliteitsmetingen/trunk/$PROJECT/history.json
EXISTING_DATE=`(ls history.$PROJECT.[0-9\-]*.json | tail -1 | grep -oe "$DATE_REGEXP") 2> /dev/null`

# If no history file exists retrieve first one from Subversion
if [ "$EXISTING_DATE" == "" ]; then
	if [ "$QUIET" -lt "2" ]; then
		echo "info: Retrieving date of first history.json file for $PROJECT. This may take some time depending on how old the project is."
	fi
	EXISTING_DATE=`(svn log -r 1:HEAD --limit 1 $SVN_HISTORY_FILE | grep -oe "$DATE_REGEXP") 2> /dev/null`

	# Validate that a date is retrieved
	if [ "$EXISTING_DATE" == "" ]; then
		echo "error: Project $PROJECT does not seem to have an entry for the file: history.json"
		echo "error: The searched location is: $SVN_HISTORY_FILE"
		exit 1
	else
		# Create empty history file for the date found
		touch history.$PROJECT.$EXISTING_DATE.json
		if [ "$QUIET" -lt "2" ]; then
			echo "info: Found history file in subversion dated $EXISTING_DATE (empty local file generated)"
		fi
	fi
else
	if [ "$QUIET" -lt "2" ]; then
		echo "info: Found local history file dated $EXISTING_DATE"
	fi
fi

# Explain status with respect to date retrieved
TODAY=`date +%Y-%m-%d`
if [ "$QUIET" -lt "1" ]; then
	echo "debug: Retrieving history from $EXISTING_DATE onwards (until today $TODAY) with delta $DELTA"
fi

# Perform retrieval of old history file
FOUND_HISTORY=
if [ "$EXISTING_DATE" \< "$TODAY" ]; then

	# Check last date in history file (assuming content is ordered chronologically)
	NEW_DATE=`tail -5 history.$PROJECT.$EXISTING_DATE.json | grep -oe "$DATE_REGEXP" | tail -1`
	if [ "$NEW_DATE" == "" ]; then
		NEW_DATE="$EXISTING_DATE"
	elif [ "$NEW_DATE" \< "$EXISTING_DATE" ]; then

		# Sometimes a date may be missing data, do not repeat ourselves with retrieving old data
		NEW_DATE="$EXISTING_DATE"
	fi

	# Add 4 extra days to retrieve newer history data
	NEW_DATE=`date --date="$NEW_DATE + $DELTA days" +"%Y-%m-%d"`
	if [ "$NEW_DATE" \> "$TODAY" ]; then
		NEW_DATE="$TODAY"
	fi

	# Retrieve newer history in temporary file
	# Only save the lines containing full data instead of summary data.
	# This is recognized by the field "date" which is present (double quotes are required!).
	if [ "$QUIET" -lt "1" ]; then
		echo "debug: Retrieving history.json dated $NEW_DATE from subversion"
	fi
	while [ "$FOUND_HISTORY" == "" ]; do
		SVN_DATE_OPTION=
		if [ "$NEW_DATE" \< "$TODAY" ]; then
			SVN_DATE_OPTION="-r {$NEW_DATE}"
		fi
		(svn cat $SVN_DATE_OPTION $SVN_HISTORY_FILE | grep '"date"') > history.$PROJECT.$NEW_DATE.tmp 2> /dev/null
		if [ "${PIPESTATUS[0]}" == "0" ] ; then
			FOUND_HISTORY=1
			if [ "$QUIET" -lt "1" ]; then
				echo "debug: Retrieved history file for date $NEW_DATE from subversion"
			fi
		else

			# Remove empty temporary file
			rm history.$PROJECT.$NEW_DATE.tmp

			# Try next day
			if [ "$NEW_DATE" \< "$TODAY" ]; then
				if [ "$QUIET" -lt "1" ]; then
					echo "debug: No history file for date $NEW_DATE, trying next day"
				fi
				NEW_DATE=`date --date="$NEW_DATE + 1 days" +"%Y-%m-%d"`
			else
				echo "error: Failed to retrieve current history file"
				exit 1
			fi
		fi
	done
else

	# Retrieve most recent history file
	if [ "$QUIET" -lt "1" ]; then
		echo "debug: Retrieving most recent history file from subversion"
	fi
	(svn cat $SVN_HISTORY_FILE | grep '"date"') > history.$PROJECT.$TODAY.tmp 2> /dev/null
	if [ "${PIPESTATUS[0]}" == "0" ] ; then
		FOUND_HISTORY=1
	else

		# Remove empty temporary file
		rm history.$PROJECT.$NEW_DATE.tmp

		# Show missing history
		echo "warning: No recent (current/actual) history file for $PROJECT"
	fi
fi

# Stop if no history file is found
if [ "$FOUND_HISTORY" != "1" ]; then
	echo "error: No history file found, stopping"
	exit 1
fi

# Find overlapping parts in existing and temporary file
# This is done by finding the first line of the temporary file in the existing file (lines should be unique)
EXISTING_FILE=history.$PROJECT.$EXISTING_DATE.json
TMP_FILE=history.$PROJECT.$NEW_DATE.tmp
NEW_FILE=history.$PROJECT.$NEW_DATE.new
FIRST_TIMESTAMP=`head -1 $TMP_FILE | grep -oe '"date": "[0-9: -]*"'`
LINE_NUMBER=`grep -nF "$FIRST_TIMESTAMP" $EXISTING_FILE | head -1 | sed "$EXTRACT_FIRST_NUMBER"`

# On an empty file replace all
if [ ! -s "$EXISTING_FILE" ]; then
	LINE_NUMBER="1"
fi

# Concatenate existing and newly retrieved (temporary) history file
if [[ "$LINE_NUMBER" =~ "$IS_NUMBER" ]]; then

	# Show how much will be stripped
	if [ "$QUIET" -lt "1" ]; then

		# Calculate which part should be stripped (from existing file)
		LINE_COUNT=`wc -l $EXISTING_FILE | sed "$EXTRACT_FIRST_NUMBER"`
		if [[ "$LINE_COUNT" =~ "$IS_NUMBER" ]]; then
			STRIP_COUNT=`expr $LINE_COUNT - $LINE_NUMBER + 1`
			echo "debug: Stripping $STRIP_COUNT lines (of total $LINE_COUNT lines) of overlapping history"
		else
			echo "debug: Stripped all lines from line $LINE_NUMBER"
		fi
	fi

	# Strip overlapping part from existing file and store result in new file
	LINE_NUMBER=`expr $LINE_NUMBER - 1`
	head -$LINE_NUMBER $EXISTING_FILE > $NEW_FILE

	# Append temporary file
	cat $TMP_FILE >> $NEW_FILE
else

	# No overlap, see if we can make delta smaller
	if [ "$DELTA" -gt "1" ]; then

		# Retry with a smaller delta (if running continuously)
		if [ "$RECURSIVE_CALL" != "" ]; then
			if [ "$QUIET" -lt "2" ]; then
				echo "info: No overlap in files, trying smaller delta"
			fi
			EXTRA_CALL=`echo -n $RECURSIVE_CALL | sed "s/--delta[ 	]*[0-9]*//" | sed "s/ / --once --delta 1 /"`
			/bin/bash $EXTRA_CALL
		else
			echo "warning: No overlap in files, you could try a lower delta"
		fi
	else

		# Just append both files if no overlap is found and store result in new file
		cat $EXISTING_FILE $TMP_FILE > $NEW_FILE
		if [ "$QUIET" -lt "2" ]; then
			echo "info: No overlap in files, appended the new data"
		fi

	fi
fi

# Remove temporary file
rm $TMP_FILE

# Handle new file
if [ -s "$NEW_FILE" ]; then

	# Keep new file as history file (might overwrite existing file if $NEW_DATE = $TODAY)
	mv -f $NEW_FILE history.$PROJECT.$NEW_DATE.json
	if [ "$QUIET" -lt "2" ]; then
		echo "info: New history file created for $NEW_DATE"
	fi

	# If new file is created succesfully, remove existing file
	if [ -s history.$PROJECT.$NEW_DATE.json ]; then
		rm $EXISTING_FILE
	fi
fi

# Recursively call script (if not already at today)
if [ "$NEW_DATE" \< "$TODAY" ]; then
	if [ "$RECURSIVE_CALL" != "" ]; then
		/bin/bash $RECURSIVE_CALL
	else
		if [ "$QUIET" -lt "2" ]; then
			echo "info: Done"
		fi
	fi
	
else
	if [ "$QUIET" -lt "2" ]; then
		echo "info: Done"
	fi
fi
